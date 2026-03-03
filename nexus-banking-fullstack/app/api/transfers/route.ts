import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { config } from "@/src/server/config";
import { mockStore } from "@/src/server/supabase";
import {
  parsePositiveAmount,
  parseCurrency,
  parseIdempotencyKey,
  parseUUID,
  ValidationError,
} from "@/src/server/validation";
import { checkRateLimit } from "@/src/server/ratelimit";
import crypto from "crypto";

export const dynamic = "force-dynamic";

/**
 * POST /api/transfers — Transfer funds between the user's own accounts.
 *
 * Implements double-entry bookkeeping: one debit + one credit entry per transfer.
 *
 * Body: {
 *   from_account_id: string,
 *   to_account_id: string,
 *   amount: number,
 *   currency: string,
 *   idempotency_key: string,
 *   description?: string
 * }
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

    const fromAccountId = parseUUID(body.from_account_id, "from_account_id");
    const toAccountId = parseUUID(body.to_account_id, "to_account_id");
    const amount = parsePositiveAmount(body.amount);
    const currency = parseCurrency(body.currency);
    const idempotencyKey = parseIdempotencyKey(body.idempotency_key);
    const description = String(body.description ?? "Internal transfer").slice(0, 500);

    if (fromAccountId === toAccountId) {
      return NextResponse.json(
        { error: "Cannot transfer to the same account" },
        { status: 400 }
      );
    }

    if (config.mockMode) {
      // Idempotency check
      if (mockStore.processedIdempotencyKeys.has(`transfer:${idempotencyKey}`)) {
        const existing = [...mockStore.transfers.values()].find(
          (t) => t.idempotency_key === idempotencyKey
        );
        return NextResponse.json({ transfer: existing, duplicate: true });
      }

      const fromAccount = mockStore.accounts.get(fromAccountId);
      const toAccount = mockStore.accounts.get(toAccountId);

      if (!fromAccount || fromAccount.user_id !== user.id) {
        return NextResponse.json({ error: "Source account not found" }, { status: 404 });
      }
      if (!toAccount || toAccount.user_id !== user.id) {
        return NextResponse.json({ error: "Destination account not found" }, { status: 404 });
      }
      if (fromAccount.available_balance < amount) {
        return NextResponse.json({ error: "Insufficient funds" }, { status: 422 });
      }

      // Execute double-entry transfer
      fromAccount.balance -= amount;
      fromAccount.available_balance -= amount;
      toAccount.balance += amount;
      toAccount.available_balance += amount;

      const transferId = crypto.randomUUID();
      const now = new Date().toISOString();

      const transfer = {
        id: transferId,
        user_id: user.id,
        from_account_id: fromAccountId,
        to_account_id: toAccountId,
        amount,
        currency,
        status: "completed",
        idempotency_key: idempotencyKey,
        description,
        created_at: now,
      };

      mockStore.transfers.set(transferId, transfer);
      mockStore.processedIdempotencyKeys.add(`transfer:${idempotencyKey}`);

      // Debit entry (from)
      mockStore.ledgerEntries.push({
        id: crypto.randomUUID(),
        account_id: fromAccountId,
        entry_type: "debit",
        amount,
        balance_after: fromAccount.balance,
        reference_type: "transfer",
        reference_id: transferId,
        description: `Transfer out: ${description}`,
        created_at: now,
      });

      // Credit entry (to)
      mockStore.ledgerEntries.push({
        id: crypto.randomUUID(),
        account_id: toAccountId,
        entry_type: "credit",
        amount,
        balance_after: toAccount.balance,
        reference_type: "transfer",
        reference_id: transferId,
        description: `Transfer in: ${description}`,
        created_at: now,
      });

      mockStore.operations.push({
        id: crypto.randomUUID(),
        actor: user.id,
        action: "create_transfer",
        entity_type: "transfer",
        entity_id: transferId,
        details: { amount, currency, from: fromAccountId, to: toAccountId },
        created_at: now,
      });

      return NextResponse.json({ transfer }, { status: 201 });
    }

    // Production: Supabase (transactional via RPC or sequential)
    const { getServerSupabase } = await import("@/src/server/supabase");
    const supabase = getServerSupabase();

    // Verify both accounts belong to user
    const { data: accounts, error: acctErr } = await supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .in("id", [fromAccountId, toAccountId]);

    if (acctErr || !accounts || accounts.length !== 2) {
      return NextResponse.json({ error: "One or both accounts not found" }, { status: 404 });
    }

    const fromAccount = accounts.find((a) => a.id === fromAccountId)!;
    const toAccount = accounts.find((a) => a.id === toAccountId)!;

    if (Number(fromAccount.available_balance) < amount) {
      return NextResponse.json({ error: "Insufficient funds" }, { status: 422 });
    }

    // Create transfer record
    const { data: transfer, error: txErr } = await supabase
      .from("transfers")
      .insert({
        user_id: user.id,
        from_account_id: fromAccountId,
        to_account_id: toAccountId,
        amount,
        currency,
        status: "completed",
        idempotency_key: idempotencyKey,
        description,
        completed_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (txErr) {
      if (txErr.code === "23505") {
        const { data: existing } = await supabase
          .from("transfers")
          .select("*")
          .eq("idempotency_key", idempotencyKey)
          .single();
        return NextResponse.json({ transfer: existing, duplicate: true });
      }
      throw txErr;
    }

    // Update balances
    const newFromBalance = Number(fromAccount.balance) - amount;
    const newFromAvailable = Number(fromAccount.available_balance) - amount;
    const newToBalance = Number(toAccount.balance) + amount;
    const newToAvailable = Number(toAccount.available_balance) + amount;

    await supabase.from("accounts").update({
      balance: newFromBalance,
      available_balance: newFromAvailable,
    }).eq("id", fromAccountId);

    await supabase.from("accounts").update({
      balance: newToBalance,
      available_balance: newToAvailable,
    }).eq("id", toAccountId);

    // Double-entry ledger
    await supabase.from("ledger_entries").insert([
      {
        account_id: fromAccountId,
        entry_type: "debit",
        amount,
        balance_after: newFromBalance,
        reference_type: "transfer",
        reference_id: transfer.id,
        description: `Transfer out: ${description}`,
      },
      {
        account_id: toAccountId,
        entry_type: "credit",
        amount,
        balance_after: newToBalance,
        reference_type: "transfer",
        reference_id: transfer.id,
        description: `Transfer in: ${description}`,
      },
    ]);

    await supabase.from("operations_log").insert({
      actor: user.id,
      action: "create_transfer",
      entity_type: "transfer",
      entity_id: transfer.id,
      details: { amount, currency, from: fromAccountId, to: toAccountId },
    });

    return NextResponse.json({ transfer }, { status: 201 });
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
  console.error("[transfers]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
