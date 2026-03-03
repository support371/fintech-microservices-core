import { NextRequest, NextResponse } from "next/server";
import { requireAdmin, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";

export const dynamic = "force-dynamic";

/**
 * GET /api/admin/operations — List recent operations log entries.
 *
 * Requires admin-level access. Returns the most recent 50 entries
 * with optional filtering by entity_type or action.
 *
 * Query params:
 *   - entity_type: Filter by entity type (e.g., "deposit", "transfer")
 *   - action: Filter by action (e.g., "create_deposit", "exchange_btc")
 *   - limit: Number of entries to return (max 100, default 50)
 */
export async function GET(req: NextRequest) {
  try {
    await requireAdmin(req);

    const { searchParams } = req.nextUrl;
    const entityType = searchParams.get("entity_type");
    const action = searchParams.get("action");
    const limit = Math.min(Number(searchParams.get("limit") ?? 50), 100);

    if (config.mockMode) {
      let operations = mockStore.getRecentOperations(100);

      if (entityType) {
        operations = operations.filter((op) => op.entity_type === entityType);
      }
      if (action) {
        operations = operations.filter((op) => op.action === action);
      }

      operations = operations.slice(0, limit);

      const summary = {
        total_deposits: mockStore.deposits.size,
        total_transfers: mockStore.transfers.size,
        total_cards: mockStore.cards.size,
        total_exchanges: mockStore.exchangeOrders.size,
        pending_notifications: mockStore.notifications.filter((n) => n.status === "pending").length,
        unprocessed_webhooks: [...mockStore.webhookEvents.values()].filter((w) => !w.processed).length,
      };

      return NextResponse.json({ operations, summary, count: operations.length });
    }

    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    let query = supabase
      .from("operations_log")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(limit);

    if (entityType) query = query.eq("entity_type", entityType);
    if (action) query = query.eq("action", action);

    const { data: operations, error } = await query;
    if (error) throw error;

    // Aggregate summary
    const [deposits, transfers, cards, exchanges, pendingNotifs, unprocessedWebhooks] =
      await Promise.all([
        supabase.from("deposits").select("id", { count: "exact", head: true }),
        supabase.from("transfers").select("id", { count: "exact", head: true }),
        supabase.from("bitcoin_cards").select("id", { count: "exact", head: true }),
        supabase.from("exchange_orders").select("id", { count: "exact", head: true }),
        supabase
          .from("notification_outbox")
          .select("id", { count: "exact", head: true })
          .eq("status", "pending"),
        supabase
          .from("webhook_events")
          .select("id", { count: "exact", head: true })
          .eq("processed", false),
      ]);

    const summary = {
      total_deposits: deposits.count ?? 0,
      total_transfers: transfers.count ?? 0,
      total_cards: cards.count ?? 0,
      total_exchanges: exchanges.count ?? 0,
      pending_notifications: pendingNotifs.count ?? 0,
      unprocessed_webhooks: unprocessedWebhooks.count ?? 0,
    };

    return NextResponse.json({
      operations,
      summary,
      count: operations?.length ?? 0,
    });
  } catch (err) {
    if (err instanceof AuthError) {
      return NextResponse.json({ error: err.message }, { status: 401 });
    }
    console.error("[admin:operations]", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
