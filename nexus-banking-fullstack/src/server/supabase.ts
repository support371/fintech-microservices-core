import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { config } from "./config";

let serverClient: SupabaseClient | null = null;
let browserClient: SupabaseClient | null = null;

/**
 * Server-side Supabase client using the service role key.
 * Bypasses RLS — use only in API routes and server components.
 */
export function getServerSupabase(): SupabaseClient {
  if (config.mockMode) {
    throw new Error(
      "getServerSupabase() should not be called in mock mode. " +
        "Use the mock data layer instead."
    );
  }
  if (!serverClient) {
    serverClient = createClient(config.supabase.url, config.supabase.serviceRoleKey, {
      auth: { persistSession: false },
    });
  }
  return serverClient;
}

/**
 * Browser-side Supabase client using the anon key.
 * Respects RLS policies — safe for client components.
 */
export function getBrowserSupabase(): SupabaseClient {
  if (config.mockMode) {
    throw new Error(
      "getBrowserSupabase() should not be called in mock mode."
    );
  }
  if (!browserClient) {
    browserClient = createClient(config.supabase.url, config.supabase.anonKey);
  }
  return browserClient;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mock Data Layer (in-memory, for development only)
// ─────────────────────────────────────────────────────────────────────────────

export interface MockUser {
  id: string;
  auth_id: string;
  email: string;
  full_name: string;
  kyc_tier: number;
  kyc_status: string;
}

export interface MockAccount {
  id: string;
  user_id: string;
  currency: string;
  account_type: string;
  balance: number;
  available_balance: number;
  is_active: boolean;
}

export interface MockDeposit {
  id: string;
  user_id: string;
  account_id: string;
  amount: number;
  currency: string;
  status: string;
  idempotency_key: string;
  created_at: string;
}

export interface MockTransfer {
  id: string;
  user_id: string;
  from_account_id: string;
  to_account_id: string;
  amount: number;
  currency: string;
  status: string;
  idempotency_key: string;
  description: string;
  created_at: string;
}

export interface MockCard {
  id: string;
  user_id: string;
  card_number_masked: string;
  card_type: string;
  status: string;
  daily_limit: number;
  monthly_limit: number;
  idempotency_key: string;
  created_at: string;
}

export interface MockExchangeOrder {
  id: string;
  user_id: string;
  fiat_amount: number;
  fiat_currency: string;
  btc_amount: number;
  exchange_rate: number;
  status: string;
  idempotency_key: string;
  created_at: string;
}

export interface MockLedgerEntry {
  id: string;
  account_id: string;
  entry_type: "debit" | "credit";
  amount: number;
  balance_after: number;
  reference_type: string;
  reference_id: string;
  description: string;
  created_at: string;
}

export interface MockWebhookEvent {
  id: string;
  source: string;
  event_type: string;
  event_id: string;
  payload: Record<string, unknown>;
  processed: boolean;
}

export interface MockNotification {
  id: string;
  channel: string;
  recipient: string;
  subject: string;
  body: string;
  status: string;
  attempts: number;
  next_retry_at: string;
}

export interface MockOperation {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

// Seeded mock data
const MOCK_USER: MockUser = {
  id: "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  auth_id: "mock-user-1",
  email: "demo@nexus.financial",
  full_name: "Demo User",
  kyc_tier: 3,
  kyc_status: "approved",
};

const MOCK_ACCOUNTS: MockAccount[] = [
  { id: "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", user_id: MOCK_USER.id, currency: "USD", account_type: "checking", balance: 25000, available_balance: 24500, is_active: true },
  { id: "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12", user_id: MOCK_USER.id, currency: "EUR", account_type: "checking", balance: 10000, available_balance: 10000, is_active: true },
  { id: "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13", user_id: MOCK_USER.id, currency: "BTC", account_type: "bitcoin",  balance: 0.35, available_balance: 0.35, is_active: true },
];

class MockDataStore {
  users = new Map<string, MockUser>([[MOCK_USER.id, MOCK_USER]]);
  accounts = new Map<string, MockAccount>(MOCK_ACCOUNTS.map((a) => [a.id, a]));
  deposits = new Map<string, MockDeposit>();
  transfers = new Map<string, MockTransfer>();
  cards = new Map<string, MockCard>();
  exchangeOrders = new Map<string, MockExchangeOrder>();
  ledgerEntries: MockLedgerEntry[] = [];
  webhookEvents = new Map<string, MockWebhookEvent>();
  notifications: MockNotification[] = [];
  operations: MockOperation[] = [];
  processedIdempotencyKeys = new Set<string>();

  getUserByAuthId(authId: string): MockUser | undefined {
    for (const user of this.users.values()) {
      if (user.auth_id === authId) return user;
    }
    return undefined;
  }

  getAccountsByUserId(userId: string): MockAccount[] {
    return [...this.accounts.values()].filter((a) => a.user_id === userId);
  }

  getDepositsByUserId(userId: string): MockDeposit[] {
    return [...this.deposits.values()]
      .filter((d) => d.user_id === userId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  getTransfersByUserId(userId: string): MockTransfer[] {
    return [...this.transfers.values()]
      .filter((t) => t.user_id === userId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  getCardsByUserId(userId: string): MockCard[] {
    return [...this.cards.values()].filter((c) => c.user_id === userId);
  }

  getExchangeOrdersByUserId(userId: string): MockExchangeOrder[] {
    return [...this.exchangeOrders.values()]
      .filter((o) => o.user_id === userId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  hasWebhookEvent(source: string, eventId: string): boolean {
    return this.webhookEvents.has(`${source}:${eventId}`);
  }

  getRecentOperations(limit: number = 25): MockOperation[] {
    return this.operations
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, limit);
  }

  getPendingNotifications(limit: number = 25): MockNotification[] {
    const now = new Date().toISOString();
    return this.notifications
      .filter((n) => n.status === "pending" && n.next_retry_at <= now)
      .slice(0, limit);
  }
}

export const mockStore = new MockDataStore();
