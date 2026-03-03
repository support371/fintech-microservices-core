import { NextRequest, NextResponse } from "next/server";
import { verifyWebhookSignature, recordWebhookEvent, markWebhookProcessed } from "@/src/server/webhooks";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * POST /api/webhooks/kyc — Ingest KYC provider webhook events.
 *
 * Events handled:
 *   - kyc.approved: Update user KYC status and tier
 *   - kyc.rejected: Mark KYC as rejected with reason
 *   - kyc.tier_upgraded: Upgrade the user's KYC tier
 */
export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-signature") ?? req.headers.get("x-webhook-signature") ?? "";

    if (!verifyWebhookSignature("kyc", rawBody, signature)) {
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

    const isNew = await recordWebhookEvent("kyc", eventType, eventId, payload, signature);
    if (!isNew) {
      return NextResponse.json({ status: "duplicate", event_id: eventId });
    }

    const userId = String(payload.user_id ?? "");

    switch (eventType) {
      case "kyc.approved": {
        const tier = Number(payload.tier ?? 1);

        if (config.mockMode) {
          const user = mockStore.users.get(userId);
          if (user) {
            user.kyc_status = "approved";
            user.kyc_tier = tier;
          }
          mockStore.notifications.push({
            id: crypto.randomUUID(),
            channel: "email",
            recipient: user?.email ?? "",
            subject: "KYC Approved",
            body: `Your identity verification has been approved. You are now at Tier ${tier}.`,
            status: "pending",
            attempts: 0,
            next_retry_at: new Date().toISOString(),
          });
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("users")
            .update({ kyc_status: "approved", kyc_tier: tier })
            .eq("id", userId);

          const { data: profile } = await supabase
            .from("users")
            .select("email")
            .eq("id", userId)
            .single();

          if (profile) {
            await supabase.from("notification_outbox").insert({
              channel: "email",
              recipient: profile.email,
              subject: "KYC Approved",
              body: `Your identity verification has been approved. You are now at Tier ${tier}.`,
            });
          }
        }
        break;
      }

      case "kyc.rejected": {
        const reason = String(payload.reason ?? "Verification failed");

        if (config.mockMode) {
          const user = mockStore.users.get(userId);
          if (user) user.kyc_status = "rejected";
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("users")
            .update({ kyc_status: "rejected" })
            .eq("id", userId);
        }

        console.log(`[webhook:kyc] User ${userId} rejected: ${reason}`);
        break;
      }

      case "kyc.tier_upgraded": {
        const newTier = Number(payload.new_tier ?? payload.tier ?? 1);

        if (config.mockMode) {
          const user = mockStore.users.get(userId);
          if (user) user.kyc_tier = newTier;
        } else {
          const { getServerSupabase } = await import("@/src/server/supabase");
          const supabase = getServerSupabase();
          await supabase
            .from("users")
            .update({ kyc_tier: newTier })
            .eq("id", userId);
        }
        break;
      }

      default:
        console.log(`[webhook:kyc] Unhandled event type: ${eventType}`);
    }

    await markWebhookProcessed("kyc", eventId);
    return NextResponse.json({ status: "processed", event_id: eventId });
  } catch (err) {
    console.error("[webhook:kyc]", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
