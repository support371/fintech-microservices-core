/**
 * /api/deposits — Create and list fiat deposits.
 * DB-backed. Emits ledger credit on creation.
 */

import { NextRequest, NextResponse } from 'next/server';

import { requireUser } from '@/src/server/auth';
import { createDeposit, listDeposits } from '@/src/server/operations';
import { postEntry } from '@/src/server/ledger';
import { checkRateLimit } from '@/src/server/ratelimit';
import { parseCurrency, parseIdempotencyKey, parsePositiveAmount } from '@/src/server/validation';

export const dynamic = 'force-dynamic';

export function GET() {
  try {
    const user = requireUser();
    const items = listDeposits(user.id);
    return NextResponse.json({ deposits: items });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unauthorized';
    return NextResponse.json({ error: message }, { status: 401 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const user = requireUser();

    const ip = req.headers.get('x-forwarded-for') ?? req.headers.get('x-real-ip') ?? 'local';
    const limited = checkRateLimit(`deposits:${ip}`, 30, 60_000);
    if (!limited.allowed) {
      return NextResponse.json({ error: 'Rate limit exceeded' }, { status: 429 });
    }

    const body = await req.json().catch(() => ({}));
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);
    const amount = parsePositiveAmount(body.amount);
    const currency = parseCurrency(body.currency ?? 'USD');

    if (!idempotencyKey) {
      return NextResponse.json({ error: 'valid idempotency_key is required' }, { status: 400 });
    }
    if (!amount) {
      return NextResponse.json({ error: 'amount must be a positive number' }, { status: 400 });
    }
    if (!currency) {
      return NextResponse.json({ error: 'currency must be a valid 3-letter code' }, { status: 400 });
    }

    const { deposit, idempotent } = createDeposit({
      userId: user.id,
      amount,
      currency,
      idempotencyKey,
    });

    // Post a pending ledger entry (becomes settled when deposit settles)
    if (!idempotent) {
      postEntry({
        userId: user.id,
        currency,
        amount,
        direction: 'credit',
        note: `deposit:${deposit.id}`,
      });
    }

    return NextResponse.json({ deposit, idempotent }, { status: idempotent ? 200 : 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Internal error';
    const status = message === 'Clerk not wired' || message.includes('role') ? 401 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
