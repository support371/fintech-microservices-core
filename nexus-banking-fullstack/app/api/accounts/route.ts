import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import { parseCurrency, parseAccountType, ValidationError } from "@/src/server/validation";
import { checkRateLimit } from "@/src/server/ratelimit";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * GET /api/accounts — List the authenticated user's accounts.
 */
export async function GET(req: NextRequest) {
  try {
    const user = await requireUser(req);

    if (config.mockMode) {
      const accounts = mockStore.getAccountsByUserId(user.id);
      return NextResponse.json({ accounts });
    }

    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();
    const { data, error } = await supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .eq("is_active", true)
      .order("created_at", { ascending: true });

    if (error) throw error;
    return NextResponse.json({ accounts: data });
  } catch (err) {
    return handleError(err);
  }
}

/**
 * POST /api/accounts — Create a new account for the authenticated user.
 *
 * Body: { currency: string, account_type: string }
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

    const currency = parseCurrency(body.currency);
    const accountType = parseAccountType(body.account_type);

    // Bitcoin accounts must be "bitcoin" type
    if (currency === "BTC" && accountType !== "bitcoin") {
      return NextResponse.json(
        { error: "BTC accounts must use account_type 'bitcoin'" },
        { status: 400 }
      );
    }

    if (config.mockMode) {
      // Check for duplicate
      const existing = mockStore.getAccountsByUserId(user.id);
      if (existing.find((a) => a.currency === currency && a.account_type === accountType)) {
        return NextResponse.json(
          { error: "Account already exists for this currency and type" },
          { status: 409 }
        );
      }

      const account = {
        id: crypto.randomUUID(),
        user_id: user.id,
        currency,
        account_type: accountType,
        balance: 0,
        available_balance: 0,
        is_active: true,
      };
      mockStore.accounts.set(account.id, account);

      mockStore.operations.push({
        id: crypto.randomUUID(),
        actor: user.id,
        action: "create_account",
        entity_type: "account",
        entity_id: account.id,
        details: { currency, account_type: accountType },
        created_at: new Date().toISOString(),
      });

      return NextResponse.json({ account }, { status: 201 });
    }

    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    const { data, error } = await supabase
      .from("accounts")
      .insert({ user_id: user.id, currency, account_type: accountType })
      .select()
      .single();

    if (error) {
      if (error.code === "23505") {
        return NextResponse.json(
          { error: "Account already exists for this currency and type" },
          { status: 409 }
        );
      }
      throw error;
    }

    await supabase.from("operations_log").insert({
      actor: user.id,
      action: "create_account",
      entity_type: "account",
      entity_id: data.id,
      details: { currency, account_type: accountType },
    });

    return NextResponse.json({ account: data }, { status: 201 });
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
  console.error("[accounts]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
