import crypto from "crypto";
import { config } from "./config";
import { mockStore } from "./supabase";

type WebhookSource = "banking" | "kyc" | "cards";

/**
 * Verify an HMAC-SHA256 webhook signature using timing-safe comparison.
 *
 * Supports two signature formats:
 *   1. Raw hex: "abcdef1234..."
 *   2. Prefixed: "sha256=abcdef1234..."
 *   3. Stripe-style: "t=timestamp,v1=signature"
 */
export function verifyWebhookSignature(
  source: WebhookSource,
  payloadRaw: string | Buffer,
  signatureHeader: string
): boolean {
  if (config.mockMode) return true;

  const secret = config.webhookSecrets[source];
  if (!secret) return false;

  const expectedMac = crypto
    .createHmac("sha256", secret)
    .update(payloadRaw)
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
