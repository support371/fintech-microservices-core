"""
Agent 1: DataIngestionAgent
============================
Ingests all relevant data streams (transaction logs, user profiles, watchlist
updates) from various sources, then normalises, deduplicates, and versions
every record before handing it downstream.

Pipeline:
  raw input → sanitise → compute checksums → deduplicate → assign version ID
            → persist IngestedRecord → emit audit event

Connects to the existing Nexus services:
  - Reads from card_platform_service (card events, KYC updates)
  - Reads from converter_service (transaction logs, webhook events)
  - Accepts watchlist file uploads for OFAC / sanctions list versioning
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from compliance_agents.shared.models import (
    AuditEventType,
    DataStreamType,
    IngestedRecord,
    WatchlistVersion,
)
from compliance_agents.shared.storage import fetch_rows, init_db, insert_row

logger = logging.getLogger(__name__)


class DataIngestionAgent:
    """
    Responsible for: normalise → deduplicate → version → persist → audit.

    Usage:
        agent = DataIngestionAgent()
        record = agent.ingest(stream_type="transaction_log", source="converter_service", raw=payload)
    """

    AGENT_NAME = "DataIngestionAgent"

    def __init__(self) -> None:
        init_db()
        logger.info("[DataIngestionAgent] Initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        stream_type: str | DataStreamType,
        source: str,
        raw: Dict[str, Any],
    ) -> IngestedRecord:
        """
        Main entry point. Accepts a raw dict, normalises it, deduplicates,
        and persists a versioned IngestedRecord.
        """
        stream_type = DataStreamType(stream_type)
        raw_bytes = json.dumps(raw, sort_keys=True, default=str).encode()
        raw_checksum = hashlib.sha256(raw_bytes).hexdigest()

        # Normalise
        normalised = self._normalise(stream_type, raw)

        # Version ID = SHA-256 of normalised payload (content-addressed)
        version_bytes = json.dumps(normalised, sort_keys=True, default=str).encode()
        version_id = hashlib.sha256(version_bytes).hexdigest()

        # Deduplicate
        is_dup, dup_of = self._check_duplicate(version_id)

        record = IngestedRecord(
            stream_type=stream_type,
            source=source,
            payload=normalised,
            raw_checksum=raw_checksum,
            version_id=version_id,
            is_duplicate=is_dup,
            duplicate_of=dup_of,
        )

        self._persist(record)

        if is_dup:
            logger.info(
                f"[DataIngestionAgent] Duplicate record detected. "
                f"version_id={version_id}, original={dup_of}"
            )
        else:
            logger.info(
                f"[DataIngestionAgent] Ingested record={record.record_id} "
                f"stream={stream_type.value} source={source}"
            )

        return record

    def ingest_watchlist(
        self,
        list_name: str,
        raw_content: bytes,
        record_count: int,
        effective_date: datetime,
        source_url: Optional[str] = None,
    ) -> WatchlistVersion:
        """
        Version a new regulatory watchlist (OFAC SDN, EU Sanctions, etc.).
        Every screening decision will reference the returned watchlist_version_id.
        """
        checksum = hashlib.sha256(raw_content).hexdigest()

        # Check if this exact version already exists (idempotent)
        existing = fetch_rows(
            "watchlist_versions",
            where="list_name = ? AND checksum = ?",
            params=[list_name, checksum],
        )
        if existing:
            wl = WatchlistVersion(**{
                **existing[0],
                "effective_date": datetime.fromisoformat(existing[0]["effective_date"]),
                "loaded_at": datetime.fromisoformat(existing[0]["loaded_at"]),
            })
            logger.info(
                f"[DataIngestionAgent] Watchlist already versioned: "
                f"list={list_name} wl_version={wl.watchlist_version_id}"
            )
            return wl

        wl = WatchlistVersion(
            list_name=list_name,
            effective_date=effective_date,
            record_count=record_count,
            checksum=checksum,
            source_url=source_url,
        )

        insert_row("watchlist_versions", {
            "watchlist_version_id": wl.watchlist_version_id,
            "list_name": wl.list_name,
            "effective_date": wl.effective_date.isoformat(),
            "record_count": wl.record_count,
            "checksum": wl.checksum,
            "source_url": wl.source_url,
            "loaded_at": wl.loaded_at.isoformat(),
        })

        logger.info(
            f"[DataIngestionAgent] New watchlist version created: "
            f"list={list_name} wl_version={wl.watchlist_version_id} "
            f"records={record_count} checksum={checksum[:16]}..."
        )
        return wl

    def get_active_watchlist(self, list_name: str) -> Optional[WatchlistVersion]:
        """Returns the most recently loaded version of a named watchlist."""
        rows = fetch_rows(
            "watchlist_versions",
            where="list_name = ?",
            params=[list_name],
            order_by="loaded_at DESC",
            limit=1,
        )
        if not rows:
            return None
        r = rows[0]
        return WatchlistVersion(
            watchlist_version_id=r["watchlist_version_id"],
            list_name=r["list_name"],
            effective_date=datetime.fromisoformat(r["effective_date"]),
            record_count=r["record_count"],
            checksum=r["checksum"],
            source_url=r["source_url"],
            loaded_at=datetime.fromisoformat(r["loaded_at"]),
        )

    def ingest_batch(
        self,
        records: List[Dict[str, Any]],
        stream_type: str | DataStreamType,
        source: str,
    ) -> List[IngestedRecord]:
        """Batch ingest — processes each record individually, returns all results."""
        results = []
        for raw in records:
            result = self.ingest(stream_type=stream_type, source=source, raw=raw)
            results.append(result)
        dupes = sum(1 for r in results if r.is_duplicate)
        logger.info(
            f"[DataIngestionAgent] Batch complete: total={len(results)} "
            f"new={len(results)-dupes} duplicates={dupes}"
        )
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalise(
        self, stream_type: DataStreamType, raw: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalise the raw payload to a canonical form.
        Strips nulls, normalises currency codes to uppercase,
        converts amount strings to floats, and ensures a UTC timestamp.
        """
        normalised: Dict[str, Any] = {}
        for k, v in raw.items():
            if v is None:
                continue
            # Currency codes always uppercase
            if k in ("currency", "fiat_currency"):
                normalised[k] = str(v).upper().strip()
            # Amounts always float
            elif k in ("amount", "fiat_amount", "btc_amount"):
                try:
                    normalised[k] = float(v)
                except (TypeError, ValueError):
                    normalised[k] = v
            # String fields stripped
            elif isinstance(v, str):
                normalised[k] = v.strip()
            else:
                normalised[k] = v

        # Ensure a canonical timestamp field exists
        if "timestamp" not in normalised:
            normalised["timestamp"] = datetime.now(timezone.utc).isoformat()
        elif isinstance(normalised.get("timestamp"), str):
            # Already a string — leave it
            pass

        # Tag the stream type for downstream agents
        normalised["_stream_type"] = stream_type.value

        return normalised

    def _check_duplicate(self, version_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a record with the same version_id (content hash) already exists.
        Returns (is_duplicate, original_record_id).
        """
        existing = fetch_rows(
            "ingested_records",
            where="version_id = ? AND is_duplicate = 0",
            params=[version_id],
            limit=1,
        )
        if existing:
            return True, existing[0]["record_id"]
        return False, None

    def _persist(self, record: IngestedRecord) -> None:
        insert_row("ingested_records", {
            "record_id":     record.record_id,
            "version_id":    record.version_id,
            "ingested_at":   record.ingested_at.isoformat(),
            "stream_type":   record.stream_type.value,
            "source":        record.source,
            "payload":       json.dumps(record.payload, default=str),
            "raw_checksum":  record.raw_checksum,
            "is_duplicate":  int(record.is_duplicate),
            "duplicate_of":  record.duplicate_of,
        })
