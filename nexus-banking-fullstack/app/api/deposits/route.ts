import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import {
  parsePositiveAmount,
  parseFiatCurrency,
  parseIdempotencyKey,
  parseUUID,
  ValidationError,
} from "@/src/server/validation";
import { checkRateLimit } from "@/src/server/ratelimit";
import { processDeposit } from "@/src/server/providers";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * GET /api/deposits — List the authenticated user's deposits.
 */
export async function GET(req: NextRequest) {
  try {
    const user = await requireUser(req);

    if (config.mockMode) {
      const deposits = mockStore.getDepositsByUserId(user.id);
      return NextResponse.json({ deposits });
    }

    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();
    const { data, error } = await supabase
      .from("deposits")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
      .limit(50);

    if (error) throw error;
    return NextResponse.json({ deposits: data });
  } catch (err) {
    return handleError(err);
  }
}

/**
 * POST /api/deposits — Create a new deposit.
 *
 * Body: { account_id: string, amount: number, currency: string, idempotency_key: string }
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

    const accountId = parseUUID(body.account_id, "account_id");
    const amount = parsePositiveAmount(body.amount);
    const currency = parseFiatCurrency(body.currency);
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);

    if (config.mockMode) {
      // Idempotency check
      if (mockStore.processedIdempotencyKeys.has(`deposit:${idempotencyKey}`)) {
        const existing = [...mockStore.deposits.values()].find(
          (d) => d.idempotency_key === idempotencyKey
        );
        return NextResponse.json({ deposit: existing, duplicate: true });
      }

      const account = mockStore.accounts.get(accountId);
      if (!account || account.user_id !== user.id) {
        return NextResponse.json({ error: "Account not found" }, { status: 404 });
      }

      // Process through provider
      const result = await processDeposit(user.id, amount, currency, idempotencyKey);

      const deposit = {
        id: crypto.randomUUID(),
        user_id: user.id,
        account_id: accountId,
        amount,
        currency,
        status: result.status,
        idempotency_key: idempotencyKey,
        created_at: new Date().toISOString(),
      };

      mockStore.deposits.set(deposit.id, deposit);
      mockStore.processedIdempotencyKeys.add(`deposit:${idempotencyKey}`);

      // Update balance if completed
      if (result.status === "completed") {
        account.balance += amount;
        account.available_balance += amount;

        // Double-entry ledger
        mockStore.ledgerEntries.push({
          id: crypto.randomUUID(),
          account_id: accountId,
          entry_type: "credit",
          amount,
          balance_after: account.balance,
          reference_type: "deposit",
          reference_id: deposit.id,
          description: `${currency} deposit via bank transfer`,
          created_at: new Date().toISOString(),
        });
      }

      // Enqueue notification
      mockStore.notifications.push({
        id: crypto.randomUUID(),
        channel: "email",
        recipient: user.email,
        subject: `Deposit ${result.status}: ${currency} ${amount.toFixed(2)}`,
        body: `Your deposit of ${currency} ${amount.toFixed(2)} has been ${result.status}.`,
        status: "pending",
        attempts: 0,
        next_retry_at: new Date().toISOString(),
      });

      mockStore.operations.push({
        id: crypto.randomUUID(),
        actor: user.id,
        action: "create_deposit",
        entity_type: "deposit",
        entity_id: deposit.id,
        details: { amount, currency, status: result.status },
        created_at: new Date().toISOString(),
      });

      return NextResponse.json({ deposit }, { status: 201 });
    }

    // Production: Supabase
    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    // Verify account ownership
    const { data: account, error: acctErr } = await supabase
      .from("accounts")
      .select("id, user_id, currency, balance, available_balance")
      .eq("id", accountId)
      .eq("user_id", user.id)
      .single();

    if (acctErr || !account) {
      return NextResponse.json({ error: "Account not found" }, { status: 404 });
    }

    const result = await processDeposit(user.id, amount, currency, idempotencyKey);

    const { data: deposit, error: depErr } = await supabase
      .from("deposits")
      .insert({
        user_id: user.id,
        account_id: accountId,
        amount,
        currency,
        status: result.status,
        idempotency_key: idempotencyKey,
        completed_at: result.status === "completed" ? new Date().toISOString() : null,
      })
      .select()
      .single();

    if (depErr) {
      if (depErr.code === "23505") {
        const { data: existing } = await supabase
          .from("deposits")
          .select("*")
          .eq("idempotency_key", idempotencyKey)
          .single();
        return NextResponse.json({ deposit: existing, duplicate: true });
      }
      throw depErr;
    }

    // Update balance and create ledger entry if completed
    if (result.status === "completed") {
      const newBalance = Number(account.balance) + amount;
      const newAvailable = Number(account.available_balance) + amount;

      await supabase
        .from("accounts")
        .update({ balance: newBalance, available_balance: newAvailable })
        .eq("id", accountId);

      await supabase.from("ledger_entries").insert({
        account_id: accountId,
        entry_type: "credit",
        amount,
        balance_after: newBalance,
        reference_type: "deposit",
        reference_id: deposit.id,
        description: `${currency} deposit via bank transfer`,
      });
    }

    // Enqueue notification
    await supabase.from("notification_outbox").insert({
      channel: "email",
      recipient: user.email,
      subject: `Deposit ${result.status}: ${currency} ${amount.toFixed(2)}`,
      body: `Your deposit of ${currency} ${amount.toFixed(2)} has been ${result.status}.`,
    });

    await supabase.from("operations_log").insert({
      actor: user.id,
      action: "create_deposit",
      entity_type: "deposit",
      entity_id: deposit.id,
      details: { amount, currency, status: result.status },
    });

    return NextResponse.json({ deposit }, { status: 201 });
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
  console.error("[deposits]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
