/**
 * Input validation utilities for API endpoints.
 */

const SUPPORTED_FIAT_CURRENCIES = new Set(["USD", "EUR", "GBP"]);
const ALL_CURRENCIES = new Set(["USD", "EUR", "GBP", "BTC"]);
const ACCOUNT_TYPES = new Set(["checking", "savings", "bitcoin"]);
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const IDEMPOTENCY_RE = /^[a-zA-Z0-9_-]{8,64}$/;

export function parsePositiveAmount(raw: unknown): number {
  const num = typeof raw === "string" ? parseFloat(raw) : Number(raw);
  if (!Number.isFinite(num) || num <= 0) {
    throw new ValidationError("Amount must be a positive number");
  }
  if (num > 10_000_000) {
    throw new ValidationError("Amount exceeds maximum allowed value");
  }
  return Math.round(num * 100) / 100;
}

export function parseBtcAmount(raw: unknown): number {
  const num = typeof raw === "string" ? parseFloat(raw) : Number(raw);
  if (!Number.isFinite(num) || num <= 0) {
    throw new ValidationError("BTC amount must be a positive number");
  }
  return Math.round(num * 1e8) / 1e8;
}

export function parseFiatCurrency(raw: unknown): string {
  const currency = String(raw).toUpperCase().trim();
  if (!SUPPORTED_FIAT_CURRENCIES.has(currency)) {
    throw new ValidationError(
      `Unsupported fiat currency: ${currency}. Supported: USD, EUR, GBP`
    );
  }
  return currency;
}

export function parseCurrency(raw: unknown): string {
  const currency = String(raw).toUpperCase().trim();
  if (!ALL_CURRENCIES.has(currency)) {
    throw new ValidationError(
      `Unsupported currency: ${currency}. Supported: USD, EUR, GBP, BTC`
    );
  }
  return currency;
}

export function parseAccountType(raw: unknown): string {
  const type = String(raw).toLowerCase().trim();
  if (!ACCOUNT_TYPES.has(type)) {
    throw new ValidationError(
      `Invalid account type: ${type}. Supported: checking, savings, bitcoin`
    );
  }
  return type;
}

export function parseIdempotencyKey(raw: unknown): string {
  const key = String(raw).trim();
  if (!IDEMPOTENCY_RE.test(key)) {
    throw new ValidationError(
      "Idempotency key must be 8-64 characters, alphanumeric with hyphens/underscores"
    );
  }
  return key;
}

export function parseUUID(raw: unknown, fieldName: string = "id"): string {
  const id = String(raw).trim();
  if (!UUID_RE.test(id)) {
    throw new ValidationError(`Invalid UUID for ${fieldName}`);
  }
  return id;
}

export function parseNonEmptyString(raw: unknown, fieldName: string): string {
  const value = String(raw ?? "").trim();
  if (value.length === 0) {
    throw new ValidationError(`${fieldName} is required`);
  }
  if (value.length > 1000) {
    throw new ValidationError(`${fieldName} exceeds maximum length (1000)`);
  }
  return value;
}

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}
