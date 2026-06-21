"""Persistent idempotency storage for conversion and webhook processing."""

from __future__ import annotations

import json
import os
import threading
from typing import Any

import psycopg2


class IdempotencyStore:
    """Claims transaction keys atomically and stores completed responses.

    PostgreSQL is mandatory when APP_ENV=production. An in-memory fallback is
    intentionally limited to development and automated tests.
    """

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.app_env = os.getenv("APP_ENV", "development").strip().lower()
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._schema_ready = False

    def _require_safe_backend(self) -> None:
        if not self.database_url and self.app_env == "production":
            raise RuntimeError("DATABASE_URL is required for production idempotency")

    def _connect(self):
        if not self.database_url:
            return None
        return psycopg2.connect(self.database_url)

    def _ensure_schema(self) -> None:
        if not self.database_url or self._schema_ready:
            return

        with self._lock:
            if self._schema_ready:
                return
            connection = self._connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            CREATE TABLE IF NOT EXISTS nexus_idempotency_keys (
                                idempotency_key TEXT PRIMARY KEY,
                                status TEXT NOT NULL,
                                response_json JSONB,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            )
                            """
                        )
                self._schema_ready = True
            finally:
                connection.close()

    def begin(self, key: str) -> bool:
        """Atomically claim a new key. Returns False for an existing key."""
        self._require_safe_backend()
        if not self.database_url:
            with self._lock:
                if key in self._memory:
                    return False
                self._memory[key] = {"status": "processing", "response": None}
                return True

        self._ensure_schema()
        connection = self._connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO nexus_idempotency_keys (idempotency_key, status)
                        VALUES (%s, 'processing')
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING idempotency_key
                        """,
                        (key,),
                    )
                    return cursor.fetchone() is not None
        finally:
            connection.close()

    def get_completed_response(self, key: str) -> dict[str, Any] | None:
        self._require_safe_backend()
        if not self.database_url:
            with self._lock:
                record = self._memory.get(key)
                if record and record["status"] == "completed":
                    return record["response"]
                return None

        self._ensure_schema()
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT response_json
                    FROM nexus_idempotency_keys
                    WHERE idempotency_key = %s AND status = 'completed'
                    """,
                    (key,),
                )
                row = cursor.fetchone()
                return row[0] if row else None
        finally:
            connection.close()

    def complete(self, key: str, response: dict[str, Any]) -> None:
        self._require_safe_backend()
        if not self.database_url:
            with self._lock:
                self._memory[key] = {"status": "completed", "response": response}
            return

        self._ensure_schema()
        connection = self._connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE nexus_idempotency_keys
                        SET status = 'completed', response_json = %s::jsonb, updated_at = NOW()
                        WHERE idempotency_key = %s
                        """,
                        (json.dumps(response, default=str), key),
                    )
        finally:
            connection.close()

    def release_failed(self, key: str) -> None:
        """Release a failed claim so a provider retry can safely try again."""
        self._require_safe_backend()
        if not self.database_url:
            with self._lock:
                self._memory.pop(key, None)
            return

        self._ensure_schema()
        connection = self._connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM nexus_idempotency_keys WHERE idempotency_key = %s AND status = 'processing'",
                        (key,),
                    )
        finally:
            connection.close()
