import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import {
  parsePositiveAmount,
  parseFiatCurrency,
  parseIdempotencyKey,
  ValidationError,
} from "@/src/server/validation";
import { checkRateLimit } from "@/src/server/ratelimit";
import { executeBtcExchange, getBtcRates } from "@/src/server/providers";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * GET /api/exchange — Get current BTC exchange rates.
 */
export async function GET() {
  const rates = getBtcRates();
  return NextResponse.json({
    rates,
    base: "BTC",
    updated_at: new Date().toISOString(),
  });
}

/**
 * POST /api/exchange — Execute a fiat-to-BTC conversion.
 *
 * Body: { fiat_amount: number, fiat_currency: string, idempotency_key: string }
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

    const fiatAmount = parsePositiveAmount(body.fiat_amount);
    const fiatCurrency = parseFiatCurrency(body.fiat_currency);
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);

    if (config.mockMode) {
      if (mockStore.processedIdempotencyKeys.has(`exchange:${idempotencyKey}`)) {
        const existing = [...mockStore.exchangeOrders.values()].find(
          (o) => o.idempotency_key === idempotencyKey
        );
        return NextResponse.json({ order: existing, duplicate: true });
      }

      // Find user's fiat and BTC accounts
      const fiatAccount = mockStore
        .getAccountsByUserId(user.id)
        .find((a) => a.currency === fiatCurrency && a.account_type === "checking");
      const btcAccount = mockStore
        .getAccountsByUserId(user.id)
        .find((a) => a.currency === "BTC");

      if (!fiatAccount) {
        return NextResponse.json(
          { error: `No ${fiatCurrency} account found` },
          { status: 404 }
        );
      }
      if (!btcAccount) {
        return NextResponse.json({ error: "No BTC account found" }, { status: 404 });
      }
      if (fiatAccount.available_balance < fiatAmount) {
        return NextResponse.json({ error: "Insufficient funds" }, { status: 422 });
      }

      const result = await executeBtcExchange(user.id, fiatAmount, fiatCurrency, idempotencyKey);

      if (result.status === "failed") {
        return NextResponse.json({ error: "Exchange failed" }, { status: 422 });
      }

      // Debit fiat, credit BTC
      fiatAccount.balance -= fiatAmount;
      fiatAccount.available_balance -= fiatAmount;
      btcAccount.balance += result.btcAmount;
      btcAccount.available_balance += result.btcAmount;

      const now = new Date().toISOString();
      const orderId = crypto.randomUUID();

      const order = {
        id: orderId,
        user_id: user.id,
        fiat_amount: fiatAmount,
        fiat_currency: fiatCurrency,
        btc_amount: result.btcAmount,
        exchange_rate: result.exchangeRate,
        status: "completed",
        idempotency_key: idempotencyKey,
        created_at: now,
      };

      mockStore.exchangeOrders.set(orderId, order);
      mockStore.processedIdempotencyKeys.add(`exchange:${idempotencyKey}`);

      // Double-entry ledger
      mockStore.ledgerEntries.push(
        {
          id: crypto.randomUUID(),
          account_id: fiatAccount.id,
          entry_type: "debit",
          amount: fiatAmount,
          balance_after: fiatAccount.balance,
          reference_type: "exchange",
          reference_id: orderId,
          description: `BTC purchase: ${fiatCurrency} ${fiatAmount}`,
          created_at: now,
        },
        {
          id: crypto.randomUUID(),
          account_id: btcAccount.id,
          entry_type: "credit",
          amount: result.btcAmount,
          balance_after: btcAccount.balance,
          reference_type: "exchange",
          reference_id: orderId,
          description: `BTC received: ${result.btcAmount} BTC`,
          created_at: now,
        }
      );

      mockStore.operations.push({
        id: crypto.randomUUID(),
        actor: user.id,
        action: "exchange_btc",
        entity_type: "exchange_order",
        entity_id: orderId,
        details: {
          fiat_amount: fiatAmount,
          fiat_currency: fiatCurrency,
          btc_amount: result.btcAmount,
          rate: result.exchangeRate,
        },
        created_at: now,
      });

      return NextResponse.json({ order }, { status: 201 });
    }

    // Production: Supabase
    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    // Find accounts
    const { data: accounts } = await supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .in("currency", [fiatCurrency, "BTC"]);

    const fiatAccount = accounts?.find(
      (a) => a.currency === fiatCurrency && a.account_type === "checking"
    );
    const btcAccount = accounts?.find((a) => a.currency === "BTC");

    if (!fiatAccount) {
      return NextResponse.json({ error: `No ${fiatCurrency} account found` }, { status: 404 });
    }
    if (!btcAccount) {
      return NextResponse.json({ error: "No BTC account found" }, { status: 404 });
    }
    if (Number(fiatAccount.available_balance) < fiatAmount) {
      return NextResponse.json({ error: "Insufficient funds" }, { status: 422 });
    }

    const result = await executeBtcExchange(user.id, fiatAmount, fiatCurrency, idempotencyKey);
    if (result.status === "failed") {
      return NextResponse.json({ error: "Exchange failed" }, { status: 422 });
    }

    const { data: order, error: orderErr } = await supabase
      .from("exchange_orders")
      .insert({
        user_id: user.id,
        fiat_amount: fiatAmount,
        fiat_currency: fiatCurrency,
        btc_amount: result.btcAmount,
        exchange_rate: result.exchangeRate,
        status: "completed",
        idempotency_key: idempotencyKey,
        completed_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (orderErr) {
      if (orderErr.code === "23505") {
        const { data: existing } = await supabase
          .from("exchange_orders")
          .select("*")
          .eq("idempotency_key", idempotencyKey)
          .single();
        return NextResponse.json({ order: existing, duplicate: true });
      }
      throw orderErr;
    }

    // Update balances
    const newFiatBalance = Number(fiatAccount.balance) - fiatAmount;
    const newBtcBalance = Number(btcAccount.balance) + result.btcAmount;

    await supabase.from("accounts").update({
      balance: newFiatBalance,
      available_balance: Number(fiatAccount.available_balance) - fiatAmount,
    }).eq("id", fiatAccount.id);

    await supabase.from("accounts").update({
      balance: newBtcBalance,
      available_balance: Number(btcAccount.available_balance) + result.btcAmount,
    }).eq("id", btcAccount.id);

    // Double-entry ledger
    await supabase.from("ledger_entries").insert([
      {
        account_id: fiatAccount.id,
        entry_type: "debit",
        amount: fiatAmount,
        balance_after: newFiatBalance,
        reference_type: "exchange",
        reference_id: order.id,
        description: `BTC purchase: ${fiatCurrency} ${fiatAmount}`,
      },
      {
        account_id: btcAccount.id,
        entry_type: "credit",
        amount: result.btcAmount,
        balance_after: newBtcBalance,
        reference_type: "exchange",
        reference_id: order.id,
        description: `BTC received: ${result.btcAmount} BTC`,
      },
    ]);

    await supabase.from("operations_log").insert({
      actor: user.id,
      action: "exchange_btc",
      entity_type: "exchange_order",
      entity_id: order.id,
      details: {
        fiat_amount: fiatAmount,
        fiat_currency: fiatCurrency,
        btc_amount: result.btcAmount,
        rate: result.exchangeRate,
      },
    });

    return NextResponse.json({ order }, { status: 201 });
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
  console.error("[exchange]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
