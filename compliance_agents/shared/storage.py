"""
Shared storage layer for the Nexus Compliance Agent System.

Uses SQLite for local/staging and is designed to be swapped for
PostgreSQL (AWS RDS) in production by changing the connection string.

IMMUTABILITY CONTRACT:
  - The `audit_log` table has NO UPDATE / DELETE operations.
  - Any attempt to mutate an audit entry is rejected at the DB layer via triggers.
  - The hash-chain verification in AuditTrailAgent validates integrity on read.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Generator, List, Optional

DB_PATH = Path(__file__).parent.parent / "nexus_compliance.db"
_lock = Lock()


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_cursor(path: Path = DB_PATH) -> Generator[sqlite3.Cursor, None, None]:
    with _lock:
        conn = get_connection(path)
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db(path: Path = DB_PATH) -> None:
    """
    Create all tables on first run.
    IMPORTANT: The audit_log table has an AFTER UPDATE / AFTER DELETE
    trigger that raises an error — enforcing append-only semantics.
    """
    with db_cursor(path) as cur:
        # ── Ingested records ────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingested_records (
                record_id       TEXT PRIMARY KEY,
                version_id      TEXT NOT NULL,
                ingested_at     TEXT NOT NULL,
                stream_type     TEXT NOT NULL,
                source          TEXT NOT NULL,
                payload         TEXT NOT NULL,   -- JSON
                raw_checksum    TEXT NOT NULL,
                is_duplicate    INTEGER NOT NULL DEFAULT 0,
                duplicate_of    TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_version ON ingested_records(version_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_stream ON ingested_records(stream_type)")

        # ── Watchlist versions ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_versions (
                watchlist_version_id TEXT PRIMARY KEY,
                list_name            TEXT NOT NULL,
                effective_date       TEXT NOT NULL,
                record_count         INTEGER NOT NULL,
                checksum             TEXT NOT NULL,
                source_url           TEXT,
                loaded_at            TEXT NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_wl_name ON watchlist_versions(list_name)")

        # ── Screening results ───────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS screening_results (
                screening_id            TEXT PRIMARY KEY,
                record_id               TEXT NOT NULL,
                watchlist_version_id    TEXT NOT NULL,
                screened_at             TEXT NOT NULL,
                rule_results            TEXT NOT NULL,   -- JSON array
                llm_analysis            TEXT,            -- JSON or NULL
                llm_model               TEXT,            -- model name for transparency
                llm_prompt_version      TEXT,            -- prompt version for traceability
                has_llm_analysis        INTEGER DEFAULT 0,
                final_risk_score        TEXT NOT NULL,
                final_decision          TEXT NOT NULL,
                decision_rationale      TEXT NOT NULL,
                FOREIGN KEY(record_id) REFERENCES ingested_records(record_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scr_record ON screening_results(record_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scr_risk ON screening_results(final_risk_score)")
        # Migration: add new columns to existing DBs (safe no-op if already present)
        for col, typedef in [
            ("llm_model",          "TEXT"),
            ("llm_prompt_version", "TEXT"),
            ("has_llm_analysis",   "INTEGER DEFAULT 0"),
        ]:
            try:
                cur.execute(f"ALTER TABLE screening_results ADD COLUMN {col} {typedef}")
            except Exception:
                pass  # column already exists

        # ── Audit log — APPEND ONLY ─────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                entry_id                TEXT PRIMARY KEY,
                sequence_number         INTEGER NOT NULL,
                prev_entry_hash         TEXT NOT NULL,
                event_type              TEXT NOT NULL,
                timestamp               TEXT NOT NULL,
                source_agent            TEXT NOT NULL,
                record_id               TEXT,
                screening_id            TEXT,
                watchlist_version_id    TEXT,
                payload                 TEXT NOT NULL,   -- JSON
                human_override          TEXT,            -- JSON or NULL
                entry_hash              TEXT NOT NULL
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_aud_seq ON audit_log(sequence_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_event ON audit_log(event_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_record ON audit_log(record_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_ts ON audit_log(timestamp)")

        # TRIGGER: Block any UPDATE on audit_log
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: audit_log entries cannot be updated');
            END
        """)

        # TRIGGER: Block any DELETE on audit_log
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: audit_log entries cannot be deleted');
            END
        """)

        # ── SAR reports ─────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sar_reports (
                sar_id                      TEXT PRIMARY KEY,
                generated_at                TEXT NOT NULL,
                generated_by_agent          TEXT NOT NULL,
                subject_user_id             TEXT NOT NULL,
                subject_name                TEXT,
                subject_account             TEXT,
                activity_start              TEXT NOT NULL,
                activity_end                TEXT NOT NULL,
                total_amount                REAL NOT NULL,
                currency                    TEXT NOT NULL,
                transaction_count           INTEGER NOT NULL,
                risk_score                  TEXT NOT NULL,
                flag_categories             TEXT NOT NULL,  -- JSON array
                narrative                   TEXT NOT NULL,
                supporting_audit_entry_ids  TEXT NOT NULL,  -- JSON array
                watchlist_version_ids_used  TEXT NOT NULL,  -- JSON array
                status                      TEXT NOT NULL DEFAULT 'draft',
                filing_reference            TEXT
            )
        """)

        # ── Compliance reports ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS compliance_reports (
                report_id                   TEXT PRIMARY KEY,
                generated_at                TEXT NOT NULL,
                period_start                TEXT NOT NULL,
                period_end                  TEXT NOT NULL,
                total_transactions          INTEGER NOT NULL,
                approved_count              INTEGER NOT NULL,
                flagged_count               INTEGER NOT NULL,
                blocked_count               INTEGER NOT NULL,
                sar_count                   INTEGER NOT NULL,
                human_override_count        INTEGER NOT NULL,
                top_risk_categories         TEXT NOT NULL,  -- JSON array
                watchlist_versions_active   TEXT NOT NULL,  -- JSON array
                audit_chain_integrity       INTEGER NOT NULL,
                report_data                 TEXT NOT NULL   -- JSON
            )
        """)


# ---------------------------------------------------------------------------
# Low-level helpers used by individual agents
# ---------------------------------------------------------------------------

def insert_row(table: str, data: Dict[str, Any], path: Path = DB_PATH) -> None:
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    with db_cursor(path) as cur:
        cur.execute(sql, list(data.values()))


def fetch_rows(
    table: str,
    where: Optional[str] = None,
    params: Optional[List[Any]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"
    with db_cursor(path) as cur:
        cur.execute(sql, params or [])
        return [dict(row) for row in cur.fetchall()]


def count_rows(
    table: str,
    where: Optional[str] = None,
    params: Optional[List[Any]] = None,
    path: Path = DB_PATH,
) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    with db_cursor(path) as cur:
        cur.execute(sql, params or [])
        return cur.fetchone()[0]
