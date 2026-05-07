import { NextRequest, NextResponse } from 'next/server';

import { requireUser } from '@/src/server/auth';
import { createDeposit, listDeposits } from '@/src/server/operations';
import { checkRateLimit } from '@/src/server/ratelimit';
import { parseCurrency, parseIdempotencyKey, parsePositiveAmount } from '@/src/server/validation';

export function GET() {
  const user = requireUser();
  const items = listDeposits(user.id);
  return NextResponse.json({ deposits: items });
}

export async function POST(req: NextRequest) {
  const user = requireUser();
  const ip = req.headers.get('x-forwarded-for') || 'local';
  const limited = checkRateLimit(`deposits:${ip}`, 30, 60_000);
  if (!limited.allowed) {
    return NextResponse.json({ error: 'Rate limit exceeded' }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const idempotencyKey = parseIdempotencyKey(body.idempotency_key);
  const amount = parsePositiveAmount(body.amount);
  const currency = parseCurrency(body.currency || 'USD');

  if (!idempotencyKey) {
    return NextResponse.json({ error: 'valid idempotency_key is required' }, { status: 400 });
  }

  if (!amount) {
    return NextResponse.json({ error: 'amount must be a positive number' }, { status: 400 });
  }

  if (!currency) {
    return NextResponse.json({ error: 'currency must be a 3-letter code' }, { status: 400 });
  }

  const { deposit, idempotent } = createDeposit({
    userId: user.id,
    amount,
    currency,
    idempotencyKey,
  });

  return NextResponse.json({ deposit, idempotent });
}
