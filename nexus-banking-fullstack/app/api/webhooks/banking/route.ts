import { NextRequest, NextResponse } from "next/server";
import { verifyWebhookSignature, recordWebhookEvent, markWebhookProcessed } from "@/src/server/webhooks";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";

export const dynamic = "force-dynamic";

/**
 * POST /api/webhooks/banking — Ingest banking provider webhook events.
 *
 * Events handled:
 *   - deposit.completed: Mark deposit as completed, credit account
 *   - deposit.failed: Mark deposit as failed
 *   - account.updated: Sync account status
 */
export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-signature") ?? req.headers.get("x-webhook-signature") ?? "";

    if (!verifyWebhookSignature("banking", rawBody, signature)) {
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

    // Deduplication
    const isNew = await recordWebhookEvent("banking", eventType, eventId, payload, signature);
    if (!isNew) {
      return NextResponse.json({ status: "duplicate", event_id: eventId });
    }

    // Process event
    switch (eventType) {
      case "deposit.completed": {
        const depositId = String(payload.deposit_id ?? "");
        const amount = Number(payload.amount ?? 0);

        if (config.mockMode) {
          const deposit = mockStore.deposits.get(depositId);
          if (deposit && deposit.status === "pending") {
            deposit.status = "completed";
            const account = mockStore.accounts.get(deposit.account_id);
            if (account) {
              account.balance += amount;
              account.available_balance += amount;
            }
          }
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("deposits")
            .update({ status: "completed", completed_at: new Date().toISOString() })
            .eq("id", depositId)
            .eq("status", "pending");
        }
        break;
      }

      case "deposit.failed": {
        const depositId = String(payload.deposit_id ?? "");
        const reason = String(payload.reason ?? "Unknown failure");

        if (config.mockMode) {
          const deposit = mockStore.deposits.get(depositId);
          if (deposit) deposit.status = "failed";
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("deposits")
            .update({ status: "failed", failure_reason: reason })
            .eq("id", depositId);
        }
        break;
      }

      default:
        console.log(`[webhook:banking] Unhandled event type: ${eventType}`);
    }

    await markWebhookProcessed("banking", eventId);
    return NextResponse.json({ status: "processed", event_id: eventId });
  } catch (err) {
    console.error("[webhook:banking]", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
