import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import { parseIdempotencyKey, ValidationError } from "@/src/server/validation";
import { checkRateLimit } from "@/src/server/ratelimit";
import { issueCard } from "@/src/server/providers";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * GET /api/cards — List the authenticated user's Bitcoin cards.
 */
export async function GET(req: NextRequest) {
  try {
    const user = await requireUser(req);

    if (config.mockMode) {
      const cards = mockStore.getCardsByUserId(user.id);
      return NextResponse.json({ cards });
    }

    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();
    const { data, error } = await supabase
      .from("bitcoin_cards")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false });

    if (error) throw error;
    return NextResponse.json({ cards: data });
  } catch (err) {
    return handleError(err);
  }
}

/**
 * POST /api/cards — Request a new Bitcoin debit card.
 *
 * Requires KYC tier >= 3. Uses the card provider (Striga) for issuance.
 *
 * Body: { card_type: "virtual" | "physical", idempotency_key: string }
 */
export async function POST(req: NextRequest) {
  try {
    const limited = checkRateLimit(req);
    if (limited) {
      return NextResponse.json(
        { error: "Rate limit exceeded" },
        { status: 429, headers: { "Retry-After": String(Math.ceil(limited.retryAfterMs / 1000)) } }
      );
    }

    const user = await requireUser(req);
    const body = await req.json();

    const cardType = body.card_type === "physical" ? "physical" : "virtual";
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);

    if (config.mockMode) {
      if (mockStore.processedIdempotencyKeys.has(`card:${idempotencyKey}`)) {
        const existing = [...mockStore.cards.values()].find(
          (c) => c.idempotency_key === idempotencyKey
        );
        return NextResponse.json({ card: existing, duplicate: true });
      }

      const result = await issueCard(user.id, user.kycTier, cardType);

      const card = {
        id: result.cardId || crypto.randomUUID(),
        user_id: user.id,
        card_number_masked: result.cardNumberMasked,
        card_type: cardType,
        status: result.status,
        daily_limit: 5000,
        monthly_limit: 50000,
        idempotency_key: idempotencyKey,
        created_at: new Date().toISOString(),
      };

      mockStore.cards.set(card.id, card);
      mockStore.processedIdempotencyKeys.add(`card:${idempotencyKey}`);

      if (result.status === "pending_kyc") {
        mockStore.notifications.push({
          id: crypto.randomUUID(),
          channel: "email",
          recipient: user.email,
          subject: "Card request pending — KYC required",
          body: "Your card request requires KYC tier 3. Please complete verification.",
          status: "pending",
          attempts: 0,
          next_retry_at: new Date().toISOString(),
        });
      }

      mockStore.operations.push({
        id: crypto.randomUUID(),
        actor: user.id,
        action: "request_card",
        entity_type: "bitcoin_card",
        entity_id: card.id,
        details: { card_type: cardType, status: result.status },
        created_at: new Date().toISOString(),
      });

      return NextResponse.json({ card }, { status: 201 });
    }

    // Production: Supabase
    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    const result = await issueCard(user.id, user.kycTier, cardType);

    const { data: card, error: cardErr } = await supabase
      .from("bitcoin_cards")
      .insert({
        user_id: user.id,
        card_number_masked: result.cardNumberMasked,
        card_type: cardType,
        status: result.status,
        idempotency_key: idempotencyKey,
        issued_at: result.status === "issued" ? new Date().toISOString() : null,
        expires_at: result.expiresAt || null,
      })
      .select()
      .single();

    if (cardErr) {
      if (cardErr.code === "23505") {
        const { data: existing } = await supabase
          .from("bitcoin_cards")
          .select("*")
          .eq("idempotency_key", idempotencyKey)
          .single();
        return NextResponse.json({ card: existing, duplicate: true });
      }
      throw cardErr;
    }

    await supabase.from("operations_log").insert({
      actor: user.id,
      action: "request_card",
      entity_type: "bitcoin_card",
      entity_id: card.id,
      details: { card_type: cardType, status: result.status },
    });

    return NextResponse.json({ card }, { status: 201 });
  } catch (err) {
    return handleError(err);
  }
}

function handleError(err: unknown) {
  if (err instanceof AuthError) {
    return NextResponse.json({ error: err.message }, { status: 401 });
  }
  if (err instanceof ValidationError) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
  console.error("[cards]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
