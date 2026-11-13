import { NextRequest, NextResponse } from "next/server";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import { sendEmail } from "@/src/server/providers";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

const BATCH_SIZE = 25;
const MAX_ATTEMPTS = 5;

/**
 * POST /api/cron/email-worker — Process the notification outbox.
 *
 * Called by Vercel Cron every 5 minutes. Processes up to 25 pending
 * notifications with exponential backoff on failures.
 *
 * Authentication: Bearer token via CRON_SECRET.
 */
export async function POST(req: NextRequest) {
  try {
    // Authenticate cron request
    const authHeader = req.headers.get("authorization");
    const expectedToken = `Bearer ${config.cronSecret}`;

    if (!config.mockMode && authHeader !== expectedToken) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    let processed = 0;
    let failed = 0;
    let skipped = 0;

    if (config.mockMode) {
      const pending = mockStore.getPendingNotifications(BATCH_SIZE);

      for (const notification of pending) {
        notification.status = "processing";
        notification.attempts += 1;

        try {
          const result = await sendEmail(
            notification.recipient,
            notification.subject,
            notification.body
          );

          if (result.sent) {
            notification.status = "sent";
            processed++;
          } else {
            throw new Error(result.error ?? "Send failed");
          }
        } catch (err) {
          if (notification.attempts >= MAX_ATTEMPTS) {
            notification.status = "failed";
            notification.last_error = String(err);
            failed++;
          } else {
            notification.status = "pending";
            // Exponential backoff: 2^attempts minutes, capped at 60 min
            const backoffMinutes = Math.min(Math.pow(2, notification.attempts), 60);
            const retryAt = new Date();
            retryAt.setMinutes(retryAt.getMinutes() + backoffMinutes);
            notification.next_retry_at = retryAt.toISOString();
            skipped++;
          }
        }
      }
    } else {
      const { getServerSupabase } = await import("@/src/server/supabase");
      const supabase = getServerSupabase();

      const { data: pending, error } = await supabase
        .from("notification_outbox")
        .select("*")
        .eq("status", "pending")
        .lte("next_retry_at", new Date().toISOString())
        .order("created_at", { ascending: true })
        .limit(BATCH_SIZE);

      if (error) throw error;

      for (const notification of pending ?? []) {
        const newAttempts = notification.attempts + 1;

        try {
          const result = await sendEmail(
            notification.recipient,
            notification.subject,
            notification.body
          );

          if (result.sent) {
            await supabase
              .from("notification_outbox")
              .update({ status: "sent", attempts: newAttempts })
              .eq("id", notification.id);
            processed++;
          } else {
            throw new Error(result.error ?? "Send failed");
          }
        } catch (err) {
          if (newAttempts >= MAX_ATTEMPTS) {
            await supabase
              .from("notification_outbox")
              .update({
                status: "failed",
                attempts: newAttempts,
                last_error: String(err),
              })
              .eq("id", notification.id);
            failed++;
          } else {
            const backoffMinutes = Math.min(Math.pow(2, newAttempts), 60);
            const retryAt = new Date();
            retryAt.setMinutes(retryAt.getMinutes() + backoffMinutes);

            await supabase
              .from("notification_outbox")
              .update({
                status: "pending",
                attempts: newAttempts,
                next_retry_at: retryAt.toISOString(),
                last_error: String(err),
              })
              .eq("id", notification.id);
            skipped++;
          }
        }
      }
    }

    return NextResponse.json({
      status: "completed",
      processed,
      failed,
      skipped,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[cron:email-worker]", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
