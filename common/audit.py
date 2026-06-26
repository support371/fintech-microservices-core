"""Append-only audit event writer for Nexus financial workflows."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import psycopg2

logger = logging.getLogger(__name__)


class AuditLogger:
    """Write structured events to PostgreSQL, with a development log fallback."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.app_env = os.getenv("APP_ENV", "development").strip().lower()

    def record(
        self,
        event_type: str,
        *,
        actor_type: str,
        actor_id: str | None = None,
        subject_id: str | None = None,
        trace_id: str | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        data = event_data or {}

        if not self.database_url:
            if self.app_env == "production":
                raise RuntimeError("DATABASE_URL is required for production audit logging")
            logger.info(
                "AUDIT event_id=%s event_type=%s actor_type=%s subject_id=%s trace_id=%s data=%s",
                event_id,
                event_type,
                actor_type,
                subject_id,
                trace_id,
                json.dumps(data, default=str, sort_keys=True),
            )
            return event_id

        connection = psycopg2.connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO nexus_ledger_events (
                            event_id,
                            event_type,
                            actor_type,
                            actor_id,
                            subject_id,
                            trace_id,
                            event_data
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            event_id,
                            event_type,
                            actor_type,
                            actor_id,
                            subject_id,
                            trace_id,
                            json.dumps(data, default=str),
                        ),
                    )
        finally:
            connection.close()

        return event_id
