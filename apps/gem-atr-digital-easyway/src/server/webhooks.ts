import crypto from 'crypto';

import { getDb } from './db';

function normalizeSignature(signature: string): string {
  return signature.startsWith('sha256=') ? signature.slice('sha256='.length) : signature;
}

export function verifyHmacSha256(secret: string, rawBody: string, signature: string): boolean {
  const normalizedSignature = normalizeSignature(signature.trim());
  if (!secret || !normalizedSignature) return false;

  const digest = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');

  if (!/^[a-f0-9]{64}$/i.test(normalizedSignature)) {
    return false;
  }

  const expected = Buffer.from(digest, 'hex');
  const provided = Buffer.from(normalizedSignature, 'hex');

  if (expected.length !== provided.length) return false;
  return crypto.timingSafeEqual(expected, provided);
}

export function recordWebhookEvent(provider: string, eventId: string, rawBody: string, signatureValid: boolean) {
  const db = getDb();
  try {
    db.prepare(
      `INSERT INTO webhook_events (provider, event_id, raw_body, signature_valid, replay)
       VALUES (?, ?, ?, ?, 0)`,
    ).run(provider, eventId, rawBody, signatureValid ? 1 : 0);

    return { replay: false };
  } catch {
    db.prepare(
      `UPDATE webhook_events SET replay = 1 WHERE provider = ? AND event_id = ?`,
    ).run(provider, eventId);
    return { replay: true };
  }
}
