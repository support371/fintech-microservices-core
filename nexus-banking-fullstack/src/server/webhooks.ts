import crypto from "crypto";
import { config } from "./config";
import { mockStore } from "./supabase";

type WebhookSource = "banking" | "kyc" | "cards";

/** Maximum age of a webhook timestamp before it's rejected (5 minutes). */
const MAX_TIMESTAMP_DRIFT_MS = 5 * 60 * 1000;

/** Set of recently seen nonces for replay detection (pruned periodically). */
const recentNonces = new Map<string, number>();

/**
 * Verify an HMAC-SHA256 webhook signature using timing-safe comparison.
 *
 * Supports signature formats:
 *   1. Raw hex: "abcdef1234..."
 *   2. Prefixed: "sha256=abcdef1234..."
 *   3. Stripe-style: "t=timestamp,v1=signature"
 *
 * Security hardening (per FATF/research recommendations):
 *   - Timestamp validation to prevent replay attacks
 *   - Nonce tracking to reject duplicate deliveries
 *   - Generic error responses to avoid leaking internal state
 */
export function verifyWebhookSignature(
  source: WebhookSource,
  payloadRaw: string | Buffer,
  signatureHeader: string,
  timestampHeader?: string | null,
  nonceHeader?: string | null
): boolean {
  if (config.mockMode) return true;

  const secret = config.webhookSecrets[source];
  if (!secret) return false;

  // ── Timestamp validation (replay attack mitigation) ──
  if (timestampHeader) {
    const ts = parseInt(timestampHeader, 10);
    if (!Number.isFinite(ts)) return false;

    const now = Math.floor(Date.now() / 1000);
    const driftMs = Math.abs(now - ts) * 1000;
    if (driftMs > MAX_TIMESTAMP_DRIFT_MS) {
      console.warn(
        `[webhook:${source}] Rejected: timestamp drift ${driftMs}ms exceeds ${MAX_TIMESTAMP_DRIFT_MS}ms`
      );
      return false;
    }
  }

  // ── Nonce deduplication (replay detection) ──
  if (nonceHeader) {
    const nonceKey = `${source}:${nonceHeader}`;
    if (recentNonces.has(nonceKey)) {
      console.warn(`[webhook:${source}] Rejected: duplicate nonce ${nonceHeader}`);
      return false;
    }
    recentNonces.set(nonceKey, Date.now());
  }

  // ── HMAC-SHA256 signature verification ──
  // If timestamp is present, include it in the signed payload (Stripe convention)
  let signedPayload: string | Buffer = payloadRaw;
  if (timestampHeader) {
    signedPayload = `${timestampHeader}.${typeof payloadRaw === "string" ? payloadRaw : payloadRaw.toString("utf8")}`;
  }

  const expectedMac = crypto
    .createHmac("sha256", secret)
    .update(signedPayload)
    .digest("hex");

  let providedSig = signatureHeader.trim();

  // Handle "sha256=..." prefix
  if (providedSig.startsWith("sha256=")) {
    providedSig = providedSig.slice(7);
  }

  // Handle Stripe-style "t=...,v1=..." format
  if (providedSig.includes(",v1=")) {
    const match = providedSig.match(/v1=([a-f0-9]+)/i);
    if (match) {
      providedSig = match[1];
    }
  }

  try {
    return crypto.timingSafeEqual(
      Buffer.from(expectedMac, "hex"),
      Buffer.from(providedSig, "hex")
    );
  } catch {
    return false;
  }
}

// Periodic nonce cleanup (every 10 minutes, discard entries older than 10 minutes)
if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const cutoff = Date.now() - 10 * 60 * 1000;
    for (const [key, timestamp] of recentNonces) {
      if (timestamp < cutoff) recentNonces.delete(key);
    }
  }, 600_000);
}

/**
 * Record a webhook event and check for duplicates.
 * Returns true if this is a new event, false if already processed.
 */
export async function recordWebhookEvent(
  source: WebhookSource,
  eventType: string,
  eventId: string,
  payload: Record<string, unknown>,
  signature: string
): Promise<boolean> {
  if (config.mockMode) {
    const key = `${source}:${eventId}`;
    if (mockStore.webhookEvents.has(key)) return false;
    mockStore.webhookEvents.set(key, {
      id: crypto.randomUUID(),
      source,
      event_type: eventType,
      event_id: eventId,
      payload,
      processed: false,
    });
    return true;
  }

  const { getServerSupabase } = await import("./supabase");
  const supabase = getServerSupabase();

  const { error } = await supabase.from("webhook_events").insert({
    source,
    event_type: eventType,
    event_id: eventId,
    payload,
    signature,
  });

  if (error) {
    // Unique constraint violation = duplicate
    if (error.code === "23505") return false;
    throw error;
  }

  return true;
}

/**
 * Mark a webhook event as successfully processed.
 */
export async function markWebhookProcessed(
  source: WebhookSource,
  eventId: string
): Promise<void> {
  if (config.mockMode) {
    const key = `${source}:${eventId}`;
    const event = mockStore.webhookEvents.get(key);
    if (event) event.processed = true;
    return;
  }

  const { getServerSupabase } = await import("./supabase");
  const supabase = getServerSupabase();
  await supabase
    .from("webhook_events")
    .update({ processed: true, processed_at: new Date().toISOString() })
    .eq("source", source)
    .eq("event_id", eventId);
}
