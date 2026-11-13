/**
 * External provider clients for banking, cards, exchange, KYC, and email.
 *
 * All providers are currently mocked for development. Each mock implementation
 * is clearly marked for replacement with real API integrations.
 */

import { config } from "./config";
import crypto from "crypto";

// ─────────────────────────────────────────────────────────────────────────────
// Banking Provider
// ─────────────────────────────────────────────────────────────────────────────

export interface DepositResult {
  transactionId: string;
  status: "completed" | "pending" | "failed";
  processedAmount: number;
  currency: string;
}

export async function processDeposit(
  userId: string,
  amount: number,
  currency: string,
  idempotencyKey: string
): Promise<DepositResult> {
  // PROVIDER INTEGRATION: Replace with real banking API call
  // e.g., Stripe, Plaid, or direct bank API using config.providers.banking
  void config.providers.banking;
  void idempotencyKey;

  await simulateLatency(100, 300);

  return {
    transactionId: `dep-${crypto.randomUUID().slice(0, 8)}`,
    status: "completed",
    processedAmount: amount,
    currency,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Card Provider (Striga-compatible interface)
// ─────────────────────────────────────────────────────────────────────────────

export interface CardIssuanceResult {
  cardId: string;
  cardNumberMasked: string;
  status: "issued" | "pending_kyc" | "failed";
  expiresAt: string;
}

export async function issueCard(
  userId: string,
  kycTier: number,
  cardType: "virtual" | "physical"
): Promise<CardIssuanceResult> {
  // PROVIDER INTEGRATION: Replace with Striga card issuance API
  // Requires KYC tier >= 3 for card issuance
  void config.providers.card;

  if (kycTier < 3) {
    return {
      cardId: "",
      cardNumberMasked: "",
      status: "pending_kyc",
      expiresAt: "",
    };
  }

  await simulateLatency(200, 500);

  const last4 = Math.floor(1000 + Math.random() * 9000);
  const expiresAt = new Date();
  expiresAt.setFullYear(expiresAt.getFullYear() + 3);

  return {
    cardId: `card-${userId.slice(0, 8)}-${crypto.randomUUID().slice(0, 4)}`,
    cardNumberMasked: `**** **** **** ${last4}`,
    status: "issued",
    expiresAt: expiresAt.toISOString(),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Exchange Provider (BTC conversion)
// ─────────────────────────────────────────────────────────────────────────────

const MOCK_BTC_RATES: Record<string, number> = {
  USD: 70000,
  EUR: 76000,
  GBP: 82000,
};

const MAX_EXCHANGE_AMOUNT = 100000;

export interface ExchangeResult {
  orderId: string;
  fiatAmount: number;
  fiatCurrency: string;
  btcAmount: number;
  exchangeRate: number;
  status: "completed" | "failed";
}

export async function executeBtcExchange(
  userId: string,
  fiatAmount: number,
  fiatCurrency: string,
  idempotencyKey: string
): Promise<ExchangeResult> {
  // PROVIDER INTEGRATION: Replace with real exchange API
  // e.g., Striga conversion or a dedicated exchange provider
  void config.providers.exchange;
  void idempotencyKey;

  if (fiatAmount > MAX_EXCHANGE_AMOUNT) {
    return {
      orderId: "",
      fiatAmount,
      fiatCurrency,
      btcAmount: 0,
      exchangeRate: 0,
      status: "failed",
    };
  }

  const rate = MOCK_BTC_RATES[fiatCurrency];
  if (!rate) {
    return {
      orderId: "",
      fiatAmount,
      fiatCurrency,
      btcAmount: 0,
      exchangeRate: 0,
      status: "failed",
    };
  }

  await simulateLatency(150, 400);

  const btcAmount = Math.round((fiatAmount / rate) * 1e8) / 1e8;

  return {
    orderId: `exch-${crypto.randomUUID().slice(0, 8)}`,
    fiatAmount,
    fiatCurrency,
    btcAmount,
    exchangeRate: rate,
    status: "completed",
  };
}

/**
 * Get current BTC exchange rates for all supported currencies.
 */
export function getBtcRates(): Record<string, number> {
  // PROVIDER INTEGRATION: Replace with real-time rate feed
  return { ...MOCK_BTC_RATES };
}

// ─────────────────────────────────────────────────────────────────────────────
// KYC Provider
// ─────────────────────────────────────────────────────────────────────────────

export interface KycVerificationResult {
  verified: boolean;
  tier: number;
  status: string;
  message: string;
}

export async function verifyKycStatus(userId: string): Promise<KycVerificationResult> {
  // PROVIDER INTEGRATION: Replace with real KYC provider API
  void config.providers.kyc;

  await simulateLatency(50, 150);

  return {
    verified: true,
    tier: 3,
    status: "approved",
    message: "KYC verification passed (mock)",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Email Provider
// ─────────────────────────────────────────────────────────────────────────────

export interface EmailResult {
  sent: boolean;
  messageId: string;
  error?: string;
}

export async function sendEmail(
  recipient: string,
  subject: string,
  body: string
): Promise<EmailResult> {
  // PROVIDER INTEGRATION: Replace with real email service
  // e.g., SendGrid, Resend, AWS SES using config.providers.email
  void config.providers.email;

  console.log(`[EMAIL MOCK] To: ${recipient} | Subject: ${subject}`);

  await simulateLatency(50, 100);

  return {
    sent: true,
    messageId: `msg-${crypto.randomUUID().slice(0, 8)}`,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function simulateLatency(minMs: number, maxMs: number): Promise<void> {
  if (!config.mockMode) return Promise.resolve();
  const ms = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
  return new Promise((resolve) => setTimeout(resolve, ms));
}
