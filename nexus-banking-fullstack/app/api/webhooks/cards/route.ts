import { NextRequest, NextResponse } from "next/server";
import { verifyWebhookSignature, recordWebhookEvent, markWebhookProcessed } from "@/src/server/webhooks";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * POST /api/webhooks/cards — Ingest card provider (Striga) webhook events.
 *
 * Events handled:
 *   - card.issued: Card successfully issued, update status
 *   - card.activated: Card activated by user
 *   - card.frozen: Card frozen (fraud or user request)
 *   - card.transaction: Card spending transaction
 */
export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-signature") ?? req.headers.get("x-webhook-signature") ?? "";
    const timestamp = req.headers.get("x-webhook-timestamp");
    const nonce = req.headers.get("x-webhook-nonce");

    if (!verifyWebhookSignature("cards", rawBody, signature, timestamp, nonce)) {
      return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
    }

    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(rawBody);
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    const eventType = String(payload.event_type ?? payload.type ?? "unknown");
    const eventId = String(payload.event_id ?? payload.id ?? "");

    if (!eventId) {
      return NextResponse.json({ error: "Missing event_id" }, { status: 400 });
    }

    const isNew = await recordWebhookEvent("cards", eventType, eventId, payload, signature);
    if (!isNew) {
      return NextResponse.json({ status: "duplicate", event_id: eventId });
    }

    const cardId = String(payload.card_id ?? "");

    switch (eventType) {
      case "card.issued": {
        const cardNumberMasked = String(payload.card_number_masked ?? "**** **** **** ????");
        const expiresAt = String(payload.expires_at ?? "");

        if (config.mockMode) {
          const card = mockStore.cards.get(cardId);
          if (card) {
            card.status = "issued";
            card.card_number_masked = cardNumberMasked;
          }
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("bitcoin_cards")
            .update({
              status: "issued",
              card_number_masked: cardNumberMasked,
              issued_at: new Date().toISOString(),
              expires_at: expiresAt || null,
            })
            .eq("id", cardId);
        }
        break;
      }

      case "card.activated": {
        if (config.mockMode) {
          const card = mockStore.cards.get(cardId);
          if (card) card.status = "active";
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("bitcoin_cards")
            .update({ status: "active" })
            .eq("id", cardId);
        }
        break;
      }

      case "card.frozen": {
        const reason = String(payload.reason ?? "Security hold");

        if (config.mockMode) {
          const card = mockStore.cards.get(cardId);
          if (card) card.status = "frozen";
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("bitcoin_cards")
            .update({ status: "frozen" })
            .eq("id", cardId);
        }

        // Notify card holder
        if (config.mockMode) {
          mockStore.notifications.push({
            id: crypto.randomUUID(),
            channel: "email",
            recipient: "user@nexus.financial",
            subject: "Card Frozen",
            body: `Your Bitcoin card has been frozen. Reason: ${reason}`,
            status: "pending",
            attempts: 0,
            next_retry_at: new Date().toISOString(),
          });
        }
        break;
      }

      case "card.transaction": {
        const amount = Number(payload.amount ?? 0);
        const currency = String(payload.currency ?? "USD");

        if (config.mockMode) {
          const card = mockStore.cards.get(cardId);
          if (card) {
            card.daily_spent = (card.daily_spent ?? 0) + amount;
            card.monthly_spent = (card.monthly_spent ?? 0) + amount;
          }
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          const { data: card } = await supabase
            .from("bitcoin_cards")
            .select("daily_spent, monthly_spent")
            .eq("id", cardId)
            .single();

          if (card) {
            await supabase
              .from("bitcoin_cards")
              .update({
                daily_spent: Number(card.daily_spent) + amount,
                monthly_spent: Number(card.monthly_spent) + amount,
              })
              .eq("id", cardId);
          }
        }

        console.log(`[webhook:cards] Transaction: ${currency} ${amount} on card ${cardId}`);
        break;
      }

      default:
        console.log(`[webhook:cards] Unhandled event type: ${eventType}`);
    }

    await markWebhookProcessed("cards", eventId);
    return NextResponse.json({ status: "processed", event_id: eventId });
  } catch (err) {
    console.error("[webhook:cards]", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
