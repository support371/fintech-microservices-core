const { env } = require('../config/env');

let pool = null;

/**
 * Lazy-initialise the PostgreSQL connection pool.
 * Falls back to in-memory storage when DATABASE_URL is not configured.
 */
function getPool() {
  if (pool) return pool;
  if (!env.DATABASE_URL) return null;

  const { Pool } = require('pg');
  pool = new Pool({ connectionString: env.DATABASE_URL });
  pool.on('error', (err) => {
    console.error('[DB] Unexpected pool error:', err);
  });
  return pool;
}

// In-memory fallback for development / sandbox without a database
const memoryLedger = [];
const memoryDedup = new Set();

/**
 * Log a webhook event to the transaction ledger.
 */
async function logEvent(entry) {
  const db = getPool();
  if (!db) {
    const key = `${entry.transaction_id}:${entry.event_type}`;
    memoryDedup.add(key);
    memoryLedger.push({
      ...entry,
      logged_at: new Date().toISOString(),
    });
    return;
  }

  await db.query(
    `INSERT INTO striga_ledger
       (transaction_id, event_type, account_id, amount, currency, exchange_rate, tx_hash, status, raw_payload)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
     ON CONFLICT (transaction_id, event_type) DO NOTHING`,
    [
      entry.transaction_id || '',
      entry.event_type || '',
      entry.account_id || '',
      entry.amount || null,
      entry.currency || '',
      entry.exchange_rate || null,
      entry.tx_hash || '',
      entry.status || '',
      JSON.stringify(entry.raw_payload || {}),
    ]
  );
}

/**
 * Check if a transaction event has already been processed (idempotency).
 */
async function isDuplicate(transactionId, eventType) {
  const db = getPool();
  if (!db) {
    return memoryDedup.has(`${transactionId}:${eventType}`);
  }

  const result = await db.query(
    `SELECT 1 FROM striga_ledger WHERE transaction_id = $1 AND event_type = $2 LIMIT 1`,
    [transactionId, eventType]
  );
  return result.rowCount > 0;
}

/**
 * Return all in-memory ledger entries (development only).
 */
function getMemoryLedger() {
  return memoryLedger;
}

module.exports = { logEvent, isDuplicate, getMemoryLedger };
