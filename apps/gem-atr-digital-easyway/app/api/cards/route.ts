import { NextRequest, NextResponse } from 'next/server';

import { requireUser } from '@/src/server/auth';
import { listCards, requestCard } from '@/src/server/operations';
import { parseIdempotencyKey } from '@/src/server/validation';

export function GET() {
  const user = requireUser();
  return NextResponse.json({ cards: listCards(user.id) });
}

export async function POST(req: NextRequest) {
  const user = requireUser();
  const body = await req.json().catch(() => ({}));

  const idempotencyKey = parseIdempotencyKey(body.idempotency_key);
  if (!idempotencyKey) {
    return NextResponse.json({ error: 'valid idempotency_key is required' }, { status: 400 });
  }

  const nickname = typeof body.nickname === 'string' && body.nickname.trim() ? body.nickname.trim() : 'GEM ATR Card';

  const result = requestCard({
    userId: user.id,
    nickname,
    idempotencyKey,
  });

  if (result.error) {
    return NextResponse.json({ error: result.error }, { status: 409 });
  }

  return NextResponse.json({ card: result.card, idempotent: result.idempotent ?? false });
}
