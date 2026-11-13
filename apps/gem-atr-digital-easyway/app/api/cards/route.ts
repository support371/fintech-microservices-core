/**
 * /api/cards — Request and list bitcoin cards.
 * DB-backed with idempotency. Calls card provider adapter.
 */

import { NextRequest, NextResponse } from 'next/server';

import { requireUser } from '@/src/server/auth';
import { listCards, requestCard, updateCardStatus } from '@/src/server/operations';
import { issueCardWithProvider } from '@/src/server/providers/card_provider';
import { parseIdempotencyKey } from '@/src/server/validation';
import { checkRateLimit } from '@/src/server/ratelimit';

export const dynamic = 'force-dynamic';

export function GET() {
  try {
    const user = requireUser();
    return NextResponse.json({ cards: listCards(user.id) });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unauthorized';
    return NextResponse.json({ error: message }, { status: 401 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const user = requireUser();

    const ip = req.headers.get('x-forwarded-for') ?? 'local';
    const limited = checkRateLimit(`cards:${user.id}`, 10, 60_000);
    if (!limited.allowed) {
      return NextResponse.json({ error: 'Rate limit exceeded' }, { status: 429 });
    }

    const body = await req.json().catch(() => ({}));
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);
    if (!idempotencyKey) {
      return NextResponse.json({ error: 'valid idempotency_key is required' }, { status: 400 });
    }

    const nickname =
      typeof body.nickname === 'string' && body.nickname.trim()
        ? body.nickname.trim().slice(0, 64)
        : 'GEM ATR Card';

    const result = requestCard({ userId: user.id, nickname, idempotencyKey });

    if (result.error) {
      return NextResponse.json({ error: result.error }, { status: 409 });
    }

    // Auto-provision with card provider if card was newly created
    if (!result.idempotent && result.card) {
      try {
        const providerResult = await issueCardWithProvider({
          userId: user.id,
          cardId: result.card.id,
          nickname,
        });

        if (providerResult.success) {
          updateCardStatus(result.card.id, 'issued', 'system');
          return NextResponse.json({
            card: { ...result.card, status: 'issued' },
            providerCardId: providerResult.providerCardId,
            maskedPan: providerResult.maskedPan,
            idempotent: false,
          }, { status: 201 });
        }
      } catch (provErr) {
        // Card record exists in DB; provider call failed — surface gracefully
        console.error('[cards/POST] Provider error:', provErr);
        return NextResponse.json({
          card: result.card,
          warning: 'Card record created but provider provisioning failed. Retry or contact support.',
          idempotent: false,
        }, { status: 202 });
      }
    }

    return NextResponse.json({ card: result.card, idempotent: result.idempotent });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Internal error';
    const status = message.includes('wired') || message.includes('role') ? 401 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
