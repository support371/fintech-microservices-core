/**
 * ledger.ts — Double-entry ledger backed by SQLite.
 * Replaces getMockLedgerSnapshot() with real DB reads.
 */

import { getDb } from './db';

export type LedgerSnapshot = {
  availableUsd: number;
  pendingUsd: number;
  btcAmount: number;
};

export type LedgerEntry = {
  id: string;
  userId: string;
  accountId: string;
  currency: string;
  amount: number;
  direction: 'credit' | 'debit';
  createdAt: string;
};

// ── Account management ────────────────────────────────────────────────────────

export function ensureAccount(userId: string, currency: string): string {
  const db = getDb();
  const existing = db
    .prepare(`SELECT id FROM ledger_accounts WHERE user_id = ? AND currency = ?`)
    .get(userId, currency) as { id: string } | undefined;

  if (existing) return existing.id;

  const id = crypto.randomUUID();
  db.prepare(
    `INSERT INTO ledger_accounts (id, user_id, currency, balance) VALUES (?, ?, ?, 0)`,
  ).run(id, userId, currency);
  return id;
}

// ── Post an entry ─────────────────────────────────────────────────────────────

export function postEntry(input: {
  userId: string;
  currency: string;
  amount: number;
  direction: 'credit' | 'debit';
  note?: string;
}): LedgerEntry {
  const db = getDb();
  const accountId = ensureAccount(input.userId, input.currency);
  const id = crypto.randomUUID();

  db.prepare(
    `INSERT INTO ledger_entries (id, user_id, account_id, currency, amount, direction)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(id, input.userId, accountId, input.currency, input.amount, input.direction);

  // Update running balance
  const delta = input.direction === 'credit' ? input.amount : -input.amount;
  db.prepare(
    `UPDATE ledger_accounts SET balance = balance + ? WHERE id = ?`,
  ).run(delta, accountId);

  return db
    .prepare(
      `SELECT id, user_id AS userId, account_id AS accountId, currency,
              amount, direction, created_at AS createdAt
       FROM ledger_entries WHERE id = ?`,
    )
    .get(id) as LedgerEntry;
}

// ── Snapshot ──────────────────────────────────────────────────────────────────

export function getLedgerSnapshot(userId: string): LedgerSnapshot {
  const db = getDb();

  // USD settled balance (from settled deposits)
  const usdAccount = db
    .prepare(
      `SELECT balance FROM ledger_accounts WHERE user_id = ? AND currency = 'USD'`,
    )
    .get(userId) as { balance: number } | undefined;

  // Pending deposits not yet settled
  const pendingRow = db
    .prepare(
      `SELECT COALESCE(SUM(amount), 0) AS total
       FROM deposits
       WHERE user_id = ? AND currency = 'USD' AND status IN ('created','received')`,
    )
    .get(userId) as { total: number };

  // BTC balance
  const btcAccount = db
    .prepare(
      `SELECT balance FROM ledger_accounts WHERE user_id = ? AND currency = 'BTC'`,
    )
    .get(userId) as { balance: number } | undefined;

  return {
    availableUsd: usdAccount?.balance ?? 0,
    pendingUsd: pendingRow.total,
    btcAmount: btcAccount?.balance ?? 0,
  };
}

export function listLedgerEntries(userId: string, limit = 50): LedgerEntry[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT id, user_id AS userId, account_id AS accountId, currency,
              amount, direction, created_at AS createdAt
       FROM ledger_entries
       WHERE user_id = ?
       ORDER BY created_at DESC
       LIMIT ?`,
    )
    .all(userId, limit) as LedgerEntry[];
}
