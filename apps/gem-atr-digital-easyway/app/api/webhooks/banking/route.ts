import { NextRequest, NextResponse } from 'next/server';

import { getConfig } from '@/src/server/config';
import { recordWebhookEvent, verifyHmacSha256 } from '@/src/server/webhooks';

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const eventId = req.headers.get('x-event-id') || '';
  const signature = req.headers.get('x-signature') || '';
  const idempotencyKey = req.headers.get('x-idempotency-key') || eventId;

  if (!eventId || !idempotencyKey) {
    return NextResponse.json({ error: 'x-event-id header is required' }, { status: 400 });
  }

  const secret = getConfig().bankingWebhookSecret;
  const signatureValid = verifyHmacSha256(secret, rawBody, signature);
  const persisted = recordWebhookEvent('banking', eventId, rawBody, signatureValid);

  if (!signatureValid) {
    return NextResponse.json({ error: 'Invalid signature', replay: persisted.replay }, { status: 401 });
  }

  return NextResponse.json({ ok: true, replay: persisted.replay, signatureValid: true, idempotencyKey });
}
