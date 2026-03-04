/**
 * Data-protection and privacy utilities.
 *
 * Implements data subject request handling for GDPR, CCPA, and LGPD.
 * Provides data minimisation helpers and consent management.
 */

import { config } from "./config";
import { mockStore, type MockUser } from "./supabase";
import crypto from "crypto";

// ─────────────────────────────────────────────────────────────────────────────
// Data Subject Request Types
// ─────────────────────────────────────────────────────────────────────────────

export type DSRType = "access" | "rectification" | "deletion" | "portability" | "restriction";

export interface DataSubjectRequest {
  id: string;
  userId: string;
  type: DSRType;
  status: "pending" | "processing" | "completed" | "denied";
  requestedAt: string;
  completedAt?: string;
  response?: Record<string, unknown>;
  denialReason?: string;
}

export interface PersonalDataExport {
  user: {
    id: string;
    email: string;
    full_name: string;
    kyc_tier: number;
    kyc_status: string;
  };
  accounts: Array<{
    id: string;
    currency: string;
    account_type: string;
    balance: number;
  }>;
  deposits: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    created_at: string;
  }>;
  transfers: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    created_at: string;
  }>;
  cards: Array<{
    id: string;
    card_type: string;
    status: string;
    created_at: string;
  }>;
  exchange_orders: Array<{
    id: string;
    fiat_amount: number;
    fiat_currency: string;
    btc_amount: number;
    status: string;
    created_at: string;
  }>;
  exported_at: string;
  format_version: string;
}

// In-memory DSR store for mock mode
const mockDSRStore = new Map<string, DataSubjectRequest>();

// ─────────────────────────────────────────────────────────────────────────────
// Data Subject Access Request (DSAR)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Handle a right-of-access request (GDPR Art. 15 / CCPA Right to Know).
 * Returns all personal data held for the user.
 */
export async function handleAccessRequest(userId: string): Promise<PersonalDataExport> {
  if (config.mockMode) {
    const user = mockStore.users.get(userId);
    if (!user) throw new PrivacyError("User not found");

    return buildExport(user);
  }

  const { getServerSupabase } = await import("./supabase");
  const supabase = getServerSupabase();

  const { data: user, error } = await supabase
    .from("users")
    .select("*")
    .eq("id", userId)
    .single();

  if (error || !user) throw new PrivacyError("User not found");

  const [accounts, deposits, transfers, cards, orders] = await Promise.all([
    supabase.from("accounts").select("id, currency, account_type, balance").eq("user_id", userId),
    supabase.from("deposits").select("id, amount, currency, status, created_at").eq("user_id", userId),
    supabase.from("transfers").select("id, amount, currency, status, created_at").eq("user_id", userId),
    supabase.from("bitcoin_cards").select("id, card_type, status, created_at").eq("user_id", userId),
    supabase.from("exchange_orders").select("id, fiat_amount, fiat_currency, btc_amount, status, created_at").eq("user_id", userId),
  ]);

  return {
    user: {
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      kyc_tier: user.kyc_tier,
      kyc_status: user.kyc_status,
    },
    accounts: accounts.data ?? [],
    deposits: deposits.data ?? [],
    transfers: transfers.data ?? [],
    cards: cards.data ?? [],
    exchange_orders: orders.data ?? [],
    exported_at: new Date().toISOString(),
    format_version: "1.0",
  };
}

/**
 * Handle a right-to-erasure request (GDPR Art. 17 / CCPA Right to Delete).
 *
 * Financial records required for regulatory compliance are retained
 * but personal identifiers are anonymised per GDPR Art. 17(3)(b).
 */
export async function handleDeletionRequest(userId: string): Promise<{
  anonymised: boolean;
  retainedRecords: string[];
}> {
  const retainedRecords: string[] = [];

  if (config.mockMode) {
    const user = mockStore.users.get(userId);
    if (!user) throw new PrivacyError("User not found");

    // Anonymise PII but retain financial records for regulatory compliance
    user.email = `deleted-${crypto.randomUUID().slice(0, 8)}@anonymised.nexus`;
    user.full_name = "[REDACTED]";
    user.auth_id = `deleted-${user.id}`;

    // Retain records required for AML audit trail (minimum 5 years)
    if (mockStore.getDepositsByUserId(userId).length > 0) retainedRecords.push("deposits");
    if (mockStore.getTransfersByUserId(userId).length > 0) retainedRecords.push("transfers");
    if (mockStore.getExchangeOrdersByUserId(userId).length > 0) retainedRecords.push("exchange_orders");
    retainedRecords.push("ledger_entries", "operations_log");

    return { anonymised: true, retainedRecords };
  }

  const { getServerSupabase } = await import("./supabase");
  const supabase = getServerSupabase();

  // Anonymise user PII
  const anonEmail = `deleted-${crypto.randomUUID().slice(0, 8)}@anonymised.nexus`;
  await supabase.from("users").update({
    email: anonEmail,
    full_name: "[REDACTED]",
    auth_id: `deleted-${userId}`,
  }).eq("id", userId);

  // Deactivate accounts (but preserve for audit)
  await supabase.from("accounts").update({ is_active: false }).eq("user_id", userId);

  // Cancel active cards
  await supabase.from("bitcoin_cards").update({ status: "cancelled" })
    .eq("user_id", userId)
    .in("status", ["active", "issued", "requested"]);

  retainedRecords.push("deposits", "transfers", "exchange_orders", "ledger_entries", "operations_log");

  return { anonymised: true, retainedRecords };
}

/**
 * Handle a data rectification request (GDPR Art. 16).
 */
export async function handleRectificationRequest(
  userId: string,
  updates: { full_name?: string; email?: string }
): Promise<{ updated: boolean; fields: string[] }> {
  const fields: string[] = [];
  const updatePayload: Record<string, string> = {};

  if (updates.full_name) {
    updatePayload.full_name = updates.full_name.trim().slice(0, 200);
    fields.push("full_name");
  }
  if (updates.email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(updates.email)) {
      throw new PrivacyError("Invalid email format");
    }
    updatePayload.email = updates.email.trim().toLowerCase();
    fields.push("email");
  }

  if (fields.length === 0) {
    throw new PrivacyError("No valid fields to update");
  }

  if (config.mockMode) {
    const user = mockStore.users.get(userId);
    if (!user) throw new PrivacyError("User not found");
    Object.assign(user, updatePayload);
    return { updated: true, fields };
  }

  const { getServerSupabase } = await import("./supabase");
  const supabase = getServerSupabase();
  const { error } = await supabase.from("users").update(updatePayload).eq("id", userId);
  if (error) throw new PrivacyError("Failed to update user data");

  return { updated: true, fields };
}

/**
 * Handle a data portability request (GDPR Art. 20).
 * Returns data in a machine-readable JSON format.
 */
export async function handlePortabilityRequest(userId: string): Promise<PersonalDataExport> {
  // Same as access request but guaranteed JSON machine-readable format
  return handleAccessRequest(userId);
}

/**
 * Create a tracked DSR record.
 */
export function createDSR(userId: string, type: DSRType): DataSubjectRequest {
  const dsr: DataSubjectRequest = {
    id: crypto.randomUUID(),
    userId,
    type,
    status: "pending",
    requestedAt: new Date().toISOString(),
  };
  mockDSRStore.set(dsr.id, dsr);
  return dsr;
}

/**
 * Get all DSRs for a user.
 */
export function getDSRsByUser(userId: string): DataSubjectRequest[] {
  return [...mockDSRStore.values()]
    .filter((d) => d.userId === userId)
    .sort((a, b) => b.requestedAt.localeCompare(a.requestedAt));
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function buildExport(user: MockUser): PersonalDataExport {
  return {
    user: {
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      kyc_tier: user.kyc_tier,
      kyc_status: user.kyc_status,
    },
    accounts: mockStore.getAccountsByUserId(user.id).map((a) => ({
      id: a.id,
      currency: a.currency,
      account_type: a.account_type,
      balance: a.balance,
    })),
    deposits: mockStore.getDepositsByUserId(user.id).map((d) => ({
      id: d.id,
      amount: d.amount,
      currency: d.currency,
      status: d.status,
      created_at: d.created_at,
    })),
    transfers: mockStore.getTransfersByUserId(user.id).map((t) => ({
      id: t.id,
      amount: t.amount,
      currency: t.currency,
      status: t.status,
      created_at: t.created_at,
    })),
    cards: mockStore.getCardsByUserId(user.id).map((c) => ({
      id: c.id,
      card_type: c.card_type,
      status: c.status,
      created_at: c.created_at,
    })),
    exchange_orders: mockStore.getExchangeOrdersByUserId(user.id).map((o) => ({
      id: o.id,
      fiat_amount: o.fiat_amount,
      fiat_currency: o.fiat_currency,
      btc_amount: o.btc_amount,
      status: o.status,
      created_at: o.created_at,
    })),
    exported_at: new Date().toISOString(),
    format_version: "1.0",
  };
}

export class PrivacyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PrivacyError";
  }
}
