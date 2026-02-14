import { NextRequest, NextResponse } from 'next/server';

import { getConfig } from '@/src/server/config';
import { getDb } from '@/src/server/db';

const cronIdempotency = new Map<string, { processed: number; sent: number; deferred: number; failed: number; at: string }>();
const MAX_ATTEMPTS = 5;

function parseBearerToken(header: string): string {
  const match = header.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() || '';
}

function computeBackoffMinutes(attempts: number): number {
  return Math.min(60, 2 ** Math.max(1, attempts));
}

function shouldSimulateFailure(recipient: string): boolean {
  return recipient.toLowerCase().includes('fail');
}

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization') || '';
  const token = parseBearerToken(authHeader);

  if (!token || token !== getConfig().cronSecret) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const idempotencyKey = String(req.headers.get('x-idempotency-key') || body.idempotency_key || '');
  if (idempotencyKey && cronIdempotency.has(idempotencyKey)) {
    const previous = cronIdempotency.get(idempotencyKey)!;
    return NextResponse.json({ ok: true, ...previous, idempotent: true });
  }

  const db = getDb();
  const jobs = db
    .prepare(
      `SELECT id, recipient, subject, body, attempts
       FROM notification_outbox
       WHERE status = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
       ORDER BY created_at ASC
       LIMIT 25`,
    )
    .all(new Date().toISOString()) as Array<{ id: number; recipient: string; attempts: number }>;

  const now = new Date();
  const nowIso = now.toISOString();
  let sent = 0;
  let deferred = 0;
  let failed = 0;

  const markSent = db.prepare(
    `UPDATE notification_outbox
     SET status = 'sent', attempts = attempts + 1, updated_at = ?, last_error = NULL, next_attempt_at = NULL
     WHERE id = ?`,
  );

  const markRetry = db.prepare(
    `UPDATE notification_outbox
     SET attempts = attempts + 1, next_attempt_at = ?, updated_at = ?, last_error = ?
     WHERE id = ?`,
  );

  const markFailed = db.prepare(
    `UPDATE notification_outbox
     SET status = 'failed', attempts = attempts + 1, next_attempt_at = NULL, updated_at = ?, last_error = ?
     WHERE id = ?`,
  );

  const tx = db.transaction(() => {
    for (const job of jobs) {
      try {
        if (shouldSimulateFailure(job.recipient)) {
          throw new Error('Simulated email provider error');
        }

        markSent.run(nowIso, job.id);
        sent += 1;
      } catch (error) {
        const nextAttempts = job.attempts + 1;
        const message = error instanceof Error ? error.message : 'Unknown delivery error';

        if (nextAttempts >= MAX_ATTEMPTS) {
          markFailed.run(nowIso, message, job.id);
          failed += 1;
          continue;
        }

        const backoffMinutes = computeBackoffMinutes(nextAttempts);
        const nextAttemptAt = new Date(now.getTime() + backoffMinutes * 60_000).toISOString();
        markRetry.run(nextAttemptAt, nowIso, message, job.id);
        deferred += 1;
      }
    }
  });

  tx();

  const response = { ok: true, processed: jobs.length, sent, deferred, failed, at: nowIso, idempotent: false };

  if (idempotencyKey) {
    cronIdempotency.set(idempotencyKey, { processed: jobs.length, sent, deferred, failed, at: nowIso });
  }

  return NextResponse.json(response);
}
