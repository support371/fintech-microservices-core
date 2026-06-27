/**
 * operations.ts — DB-backed data layer replacing all in-memory Maps.
 * All reads/writes go through better-sqlite3 via getDb().
 */

import { getDb } from './db';

// ── Types ────────────────────────────────────────────────────────────────────

export type DepositStatus = 'created' | 'received' | 'settled';
export type CardStatus = 'requested' | 'issued' | 'frozen';

export type Deposit = {
  id: string;
  userId: string;
  amount: number;
  currency: string;
  status: DepositStatus;
  idempotencyKey: string;
  createdAt: string;
  updatedAt: string;
};

export type BitcoinCard = {
  id: string;
  userId: string;
  nickname: string;
  status: CardStatus;
  createdAt: string;
  updatedAt: string;
};

export type OperationLog = {
  id: number;
  operation: string;
  actorId: string | null;
  metadata: string | null;
  createdAt: string;
};

// ── Internal helpers ─────────────────────────────────────────────────────────

function addOperation(operation: string, actorId: string, metadata?: Record<string, unknown>) {
  const db = getDb();
  db.prepare(
    `INSERT INTO operations_log (operation, actor_id, metadata, created_at)
     VALUES (?, ?, ?, datetime('now'))`,
  ).run(operation, actorId, metadata ? JSON.stringify(metadata) : null);
}

// ── Deposits ─────────────────────────────────────────────────────────────────

export function listDeposits(userId: string): Deposit[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT id, user_id AS userId, amount, currency, status,
              idempotency_key AS idempotencyKey,
              created_at AS createdAt, updated_at AS updatedAt
       FROM deposits
       WHERE user_id = ?
       ORDER BY created_at DESC`,
    )
    .all(userId) as Deposit[];
}

export function createDeposit(input: {
  userId: string;
  amount: number;
  currency: string;
  idempotencyKey: string;
}): { deposit: Deposit; idempotent: boolean } {
  const db = getDb();

  // Idempotency check
  const existing = db
    .prepare(
      `SELECT id, user_id AS userId, amount, currency, status,
              idempotency_key AS idempotencyKey,
              created_at AS createdAt, updated_at AS updatedAt
       FROM deposits WHERE idempotency_key = ?`,
    )
    .get(input.idempotencyKey) as Deposit | undefined;

  if (existing) return { deposit: existing, idempotent: true };

  const id = crypto.randomUUID();
  db.prepare(
    `INSERT INTO deposits (id, user_id, amount, currency, status, idempotency_key)
     VALUES (?, ?, ?, ?, 'created', ?)`,
  ).run(id, input.userId, input.amount, input.currency, input.idempotencyKey);

  addOperation(`deposit_created:${id}`, input.userId, { amount: input.amount, currency: input.currency });

  const deposit = db
    .prepare(
      `SELECT id, user_id AS userId, amount, currency, status,
              idempotency_key AS idempotencyKey,
              created_at AS createdAt, updated_at AS updatedAt
       FROM deposits WHERE id = ?`,
    )
    .get(id) as Deposit;

  return { deposit, idempotent: false };
}

export function updateDepositStatus(depositId: string, status: DepositStatus, actorId: string): boolean {
  const db = getDb();
  const info = db
    .prepare(
      `UPDATE deposits SET status = ?, updated_at = datetime('now') WHERE id = ?`,
    )
    .run(status, depositId);

  if (info.changes > 0) {
    addOperation(`deposit_status_changed:${depositId}:${status}`, actorId);
    return true;
  }
  return false;
}

export function getDeposit(depositId: string): Deposit | null {
  const db = getDb();
  return (
    (db
      .prepare(
        `SELECT id, user_id AS userId, amount, currency, status,
                idempotency_key AS idempotencyKey,
                created_at AS createdAt, updated_at AS updatedAt
         FROM deposits WHERE id = ?`,
      )
      .get(depositId) as Deposit | undefined) ?? null
  );
}

// ── Bitcoin Cards ─────────────────────────────────────────────────────────────

export function listCards(userId: string): BitcoinCard[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT id, user_id AS userId, nickname, status,
              created_at AS createdAt, updated_at AS updatedAt
       FROM bitcoin_cards
       WHERE user_id = ?
       ORDER BY created_at DESC`,
    )
    .all(userId) as BitcoinCard[];
}

export function requestCard(input: {
  userId: string;
  nickname: string;
  idempotencyKey: string;
}): { card?: BitcoinCard; error?: string; idempotent?: boolean } {
  const db = getDb();

  // Idempotency via operations_log metadata
  const idempotentRow = db
    .prepare(
      `SELECT metadata FROM operations_log
       WHERE operation LIKE 'card_requested:%'
         AND actor_id = ?
         AND metadata LIKE ?
       LIMIT 1`,
    )
    .get(input.userId, `%"idempotencyKey":"${input.idempotencyKey}"%`) as
    | { metadata: string }
    | undefined;

  if (idempotentRow) {
    const meta = JSON.parse(idempotentRow.metadata);
    const card = db
      .prepare(
        `SELECT id, user_id AS userId, nickname, status,
                created_at AS createdAt, updated_at AS updatedAt
         FROM bitcoin_cards WHERE id = ?`,
      )
      .get(meta.cardId) as BitcoinCard | undefined;
    if (card) return { card, idempotent: true };
  }

  // One active card per user
  const activeCard = db
    .prepare(
      `SELECT id FROM bitcoin_cards
       WHERE user_id = ? AND status IN ('requested','issued')
       LIMIT 1`,
    )
    .get(input.userId);

  if (activeCard) {
    return { error: 'You already have an active or requested card.' };
  }

  const id = crypto.randomUUID();
  db.prepare(
    `INSERT INTO bitcoin_cards (id, user_id, nickname, status)
     VALUES (?, ?, ?, 'requested')`,
  ).run(id, input.userId, input.nickname || 'GEM ATR Card');

  addOperation(`card_requested:${id}`, input.userId, {
    cardId: id,
    idempotencyKey: input.idempotencyKey,
  });

  const card = db
    .prepare(
      `SELECT id, user_id AS userId, nickname, status,
              created_at AS createdAt, updated_at AS updatedAt
       FROM bitcoin_cards WHERE id = ?`,
    )
    .get(id) as BitcoinCard;

  return { card, idempotent: false };
}

export function updateCardStatus(cardId: string, status: CardStatus, actorId: string): boolean {
  const db = getDb();
  const info = db
    .prepare(
      `UPDATE bitcoin_cards SET status = ?, updated_at = datetime('now') WHERE id = ?`,
    )
    .run(status, cardId);

  if (info.changes > 0) {
    addOperation(`card_status_changed:${cardId}:${status}`, actorId);
    return true;
  }
  return false;
}

// ── Operations Log ────────────────────────────────────────────────────────────

export function getOperations(limit = 25): OperationLog[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT id, operation, actor_id AS actorId, metadata, created_at AS createdAt
       FROM operations_log
       ORDER BY created_at DESC
       LIMIT ?`,
    )
    .all(limit) as OperationLog[];
}

// ── Profiles ──────────────────────────────────────────────────────────────────

export function upsertProfile(id: string, email: string, role: 'user' | 'admin' = 'user'): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO profiles (id, email, role)
     VALUES (?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET email = excluded.email`,
  ).run(id, email, role);
}

export function getProfile(id: string): { id: string; email: string; role: string } | null {
  const db = getDb();
  return (
    (db.prepare(`SELECT id, email, role FROM profiles WHERE id = ?`).get(id) as
      | { id: string; email: string; role: string }
      | undefined) ?? null
  );
}
