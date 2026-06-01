"""
Agent 3: AuditTrailAgent
=========================
Creates and maintains an append-only, tamper-proof audit log for every
decision, flag, action, and human override in the Nexus compliance system.

IMMUTABILITY GUARANTEES:
  1. Database-level: SQLite triggers ABORT any UPDATE or DELETE on audit_log.
  2. Application-level: This agent has NO update/delete methods — only append.
  3. Hash-chain: Each entry contains prev_entry_hash (SHA-256 of the prior entry).
     Any tampering breaks the chain and is detected by verify_chain_integrity().
  4. Sequence numbers: Monotonically increasing, with gap detection.

HUMAN OVERRIDE POLICY:
  Every human override MUST include a documented rationale (min 10 chars).
  Rationale is stored verbatim in the audit entry payload — it cannot be
  changed after the fact. This directly addresses the "audit exposure" concern.

QUERYABILITY:
  Auditors can query by: record_id, event_type, date range, risk score,
  user_id, screening_id, watchlist_version_id, and human_override presence.

GOVERNANCE EVENT EMISSION (v1.1):
  record_screening_decision() now emits up to three discrete audit entries:
    1. rule_screening_complete  — always emitted (satisfies COSO-CA.03)
    2. llm_analysis_complete    — emitted only when LLM ran (satisfies GAO-AI-TR.04)
    3. transaction_approved/flagged/blocked — the final decision record
  This gives framework controls direct, queryable evidence entries.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from compliance_agents.shared.models import (
    AuditEntry,
    AuditEventType,
    HumanOverride,
    IngestedRecord,
    OverrideAction,
    ScreeningResult,
    ScreeningRuleResult,
)
from compliance_agents.shared.storage import (
    count_rows,
    db_cursor,
    fetch_rows,
    init_db,
    insert_row,
)

logger = logging.getLogger(__name__)

# The genesis hash — the "prev" hash for the very first entry
GENESIS_HASH = hashlib.sha256(b"nexus-audit-chain-genesis-v1").hexdigest()


class AuditTrailAgent:
    """
    Append-only audit log manager.

    Usage:
        agent = AuditTrailAgent()
        entries = agent.record_screening_decision(record, screening_result)
        entry   = agent.record_human_override(screening_result, override)
    """

    AGENT_NAME = "AuditTrailAgent"

    def __init__(self) -> None:
        init_db()
        logger.info("[AuditTrailAgent] Initialised.")

    # ------------------------------------------------------------------
    # Convenience recorders (typed wrappers around _append)
    # ------------------------------------------------------------------

    def record_ingestion(self, record: IngestedRecord) -> AuditEntry:
        """Record that a new data record was ingested."""
        event_type = (
            AuditEventType.DATA_DEDUPLICATED
            if record.is_duplicate
            else AuditEventType.DATA_INGESTED
        )
        return self._append(
            event_type=event_type,
            source_agent="DataIngestionAgent",
            record_id=record.record_id,
            payload={
                "stream_type":  record.stream_type.value,
                "source":       record.source,
                "version_id":   record.version_id,
                "raw_checksum": record.raw_checksum,
                "is_duplicate": record.is_duplicate,
                "duplicate_of": record.duplicate_of,
                "ingested_at":  record.ingested_at.isoformat(),
            },
        )

    def record_screening_decision(
        self,
        record: IngestedRecord,
        result: ScreeningResult,
    ) -> Tuple[AuditEntry, ...]:
        """
        Record the full screening context as discrete, framework-mapped entries.

        Emits (in order):
          1. rule_screening_complete  — always; satisfies COSO-CA.03, COBIT-DSS06.06
          2. llm_analysis_complete    — only if LLM ran; satisfies GAO-AI-TR.04, IIA-AI-ETH.01
          3. transaction_*            — final decision; satisfies GAO-AI-ACC.01, COSO-RC.05

        Returns a tuple of all entries emitted (1–3 entries).
        Callers that only need the decision entry can use result[-1].
        """
        emitted: List[AuditEntry] = []

        # ── Entry 1: Rule screening complete ──────────────────────────
        rule_payload: Dict[str, Any] = {
            "screening_id":         result.screening_id,
            "watchlist_version_id": result.watchlist_version_id,
            "rule_results": [
                {
                    "rule_id":         r.rule_id,
                    "rule_name":       r.rule_name,
                    "result":          r.result.value,
                    "detail":          r.detail,
                    "triggered_value": r.triggered_value,
                    "threshold":       r.threshold,
                }
                for r in result.rule_results
            ],
            "rule_aggregate_decision": result.final_decision.value,
            "rules_triggered_count": sum(
                1 for r in result.rule_results
                if r.result != ScreeningRuleResult.PASS
            ),
        }
        emitted.append(self._append(
            event_type=AuditEventType.RULE_SCREENING_COMPLETE,
            source_agent="ScreeningAgent",
            record_id=record.record_id,
            screening_id=result.screening_id,
            watchlist_version_id=result.watchlist_version_id,
            payload=rule_payload,
        ))

        # ── Entry 2: LLM analysis complete (only if LLM ran) ─────────
        if result.llm_analysis:
            llm_payload: Dict[str, Any] = {
                "screening_id":         result.screening_id,
                "watchlist_version_id": result.watchlist_version_id,
                # Full model provenance — required for GAO-AI-TR.04
                "model":                result.llm_analysis.model,
                "prompt_version":       result.llm_analysis.prompt_version,
                "risk_score":           result.llm_analysis.risk_score.value,
                "confidence":           result.llm_analysis.confidence,
                "flags":                result.llm_analysis.flags,
                "narrative":            result.llm_analysis.narrative,
                "raw_response":         result.llm_analysis.raw_response,   # verbatim — never truncated
                "analysed_at":          result.llm_analysis.analysed_at.isoformat(),
            }
            emitted.append(self._append(
                event_type=AuditEventType.LLM_ANALYSIS_COMPLETE,
                source_agent="ScreeningAgent",
                record_id=record.record_id,
                screening_id=result.screening_id,
                watchlist_version_id=result.watchlist_version_id,
                payload=llm_payload,
            ))

        # ── Entry 3: Final decision ───────────────────────────────────
        event_map = {
            ScreeningRuleResult.PASS:  AuditEventType.TRANSACTION_APPROVED,
            ScreeningRuleResult.FLAG:  AuditEventType.TRANSACTION_FLAGGED,
            ScreeningRuleResult.BLOCK: AuditEventType.TRANSACTION_BLOCKED,
        }
        decision_event = event_map.get(result.final_decision, AuditEventType.RISK_SCORE_ASSIGNED)

        decision_payload: Dict[str, Any] = {
            "screening_id":         result.screening_id,
            "watchlist_version_id": result.watchlist_version_id,
            "final_risk_score":     result.final_risk_score.value,
            "final_decision":       result.final_decision.value,
            "decision_rationale":   result.decision_rationale,
            # Embed abbreviated rule + LLM context so decision entry is self-contained
            "rule_results": [
                {
                    "rule_id":         r.rule_id,
                    "rule_name":       r.rule_name,
                    "result":          r.result.value,
                    "detail":          r.detail,
                    "triggered_value": r.triggered_value,
                    "threshold":       r.threshold,
                }
                for r in result.rule_results
            ],
            # Full transaction snapshot for auditors
            "transaction_snapshot": record.payload,
            "ingested_at":          record.ingested_at.isoformat(),
        }

        if result.llm_analysis:
            decision_payload["llm_analysis"] = {
                "model":          result.llm_analysis.model,
                "prompt_version": result.llm_analysis.prompt_version,
                "risk_score":     result.llm_analysis.risk_score.value,
                "confidence":     result.llm_analysis.confidence,
                "flags":          result.llm_analysis.flags,
                "narrative":      result.llm_analysis.narrative,
                "raw_response":   result.llm_analysis.raw_response,
                "analysed_at":    result.llm_analysis.analysed_at.isoformat(),
            }

        emitted.append(self._append(
            event_type=decision_event,
            source_agent="ScreeningAgent",
            record_id=record.record_id,
            screening_id=result.screening_id,
            watchlist_version_id=result.watchlist_version_id,
            payload=decision_payload,
        ))

        return tuple(emitted)

    def record_human_override(
        self,
        screening_result: ScreeningResult,
        actor_id: str,
        actor_email: str,
        action: str | OverrideAction,
        rationale: str,
    ) -> AuditEntry:
        """
        Record a human analyst's override of a system decision.

        The rationale parameter is MANDATORY and stored verbatim.
        Minimum 10 characters enforced by the HumanOverride model.

        This directly addresses the audit exposure concern —
        every override has a documented 'why' that cannot be changed.
        """
        action = OverrideAction(action)
        override = HumanOverride(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            rationale=rationale,
            original_decision=screening_result.final_decision,
        )

        return self._append(
            event_type=AuditEventType.HUMAN_OVERRIDE,
            source_agent="HumanAnalyst",
            record_id=screening_result.record_id,
            screening_id=screening_result.screening_id,
            watchlist_version_id=screening_result.watchlist_version_id,
            payload={
                "original_risk_score":  screening_result.final_risk_score.value,
                "original_decision":    screening_result.final_decision.value,
                "override_action":      action.value,
                "override_rationale":   rationale,    # The "why" — stored forever
                "actor_id":             actor_id,
                "actor_email":          actor_email,
                "override_id":          override.override_id,
                "override_timestamp":   override.timestamp.isoformat(),
            },
            human_override=override,
        )

    def record_sar_generation(
        self,
        sar_id: str,
        subject_user_id: str,
        risk_score: str,
        supporting_entry_ids: List[str],
    ) -> AuditEntry:
        """Record that a SAR was generated."""
        return self._append(
            event_type=AuditEventType.SAR_GENERATED,
            source_agent="ReportingAgent",
            payload={
                "sar_id":               sar_id,
                "subject_user_id":      subject_user_id,
                "risk_score":           risk_score,
                "supporting_entry_ids": supporting_entry_ids,
            },
        )

    def record_system_event(
        self,
        source_agent: str,
        detail: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Record a generic system/operational event."""
        return self._append(
            event_type=AuditEventType.SYSTEM_EVENT,
            source_agent=source_agent,
            payload={"detail": detail, **(extra or {})},
        )

    # ------------------------------------------------------------------
    # Query API (for auditors and the Reporting Agent)
    # ------------------------------------------------------------------

    def query(
        self,
        event_type: Optional[str] = None,
        record_id: Optional[str] = None,
        screening_id: Optional[str] = None,
        watchlist_version_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        human_overrides_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEntry]:
        """
        Query audit entries with rich filtering.
        Returns entries in ascending sequence order (oldest first).
        """
        conditions = []
        params: List[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if record_id:
            conditions.append("record_id = ?")
            params.append(record_id)
        if screening_id:
            conditions.append("screening_id = ?")
            params.append(screening_id)
        if watchlist_version_id:
            conditions.append("watchlist_version_id = ?")
            params.append(watchlist_version_id)
        if from_dt:
            conditions.append("timestamp >= ?")
            params.append(from_dt.isoformat())
        if to_dt:
            conditions.append("timestamp <= ?")
            params.append(to_dt.isoformat())
        if human_overrides_only:
            conditions.append("human_override IS NOT NULL")

        where = " AND ".join(conditions) if conditions else None

        rows = fetch_rows(
            "audit_log",
            where=where,
            params=params if params else None,
            order_by="sequence_number ASC",
            limit=limit + offset,
        )
        rows = rows[offset:]

        return [self._row_to_entry(r) for r in rows]

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verify the hash-chain integrity of the entire audit log.
        Returns a report indicating any broken links or tampered entries.
        """
        rows = fetch_rows("audit_log", order_by="sequence_number ASC")
        if not rows:
            return {"status": "empty", "verified_entries": 0, "broken_links": [], "integrity_ok": True}

        broken_links = []
        prev_hash = GENESIS_HASH
        prev_seq = 0

        for row in rows:
            entry = self._row_to_entry(row)

            # Check sequence continuity
            if entry.sequence_number != prev_seq + 1:
                broken_links.append({
                    "entry_id":        entry.entry_id,
                    "sequence_number": entry.sequence_number,
                    "issue": f"Sequence gap: expected {prev_seq + 1}, got {entry.sequence_number}",
                })

            # Check prev_entry_hash link
            if entry.prev_entry_hash != prev_hash:
                broken_links.append({
                    "entry_id":        entry.entry_id,
                    "sequence_number": entry.sequence_number,
                    "issue": "prev_entry_hash mismatch — chain broken or entry tampered",
                })

            # Re-compute and verify entry_hash
            recomputed = entry.compute_hash()
            if recomputed != entry.entry_hash:
                broken_links.append({
                    "entry_id":        entry.entry_id,
                    "sequence_number": entry.sequence_number,
                    "issue": "entry_hash mismatch — entry content has been tampered",
                })

            prev_hash = entry.entry_hash or recomputed
            prev_seq  = entry.sequence_number

        integrity_ok = len(broken_links) == 0
        logger.info(
            "[AuditTrailAgent] Chain integrity verified: entries=%d broken=%d ok=%s",
            len(rows), len(broken_links), integrity_ok,
        )
        return {
            "status":           "ok" if integrity_ok else "INTEGRITY_VIOLATION",
            "verified_entries": len(rows),
            "broken_links":     broken_links,
            "integrity_ok":     integrity_ok,
        }

    # ------------------------------------------------------------------
    # Core append operation — the ONLY write path
    # ------------------------------------------------------------------

    def _append(
        self,
        event_type: AuditEventType,
        source_agent: str,
        payload: Dict[str, Any],
        record_id: Optional[str] = None,
        screening_id: Optional[str] = None,
        watchlist_version_id: Optional[str] = None,
        human_override: Optional[HumanOverride] = None,
    ) -> AuditEntry:
        """
        THE ONLY WAY to write to the audit log.
        Atomically: gets last sequence + hash, constructs entry, hashes it, inserts.
        """
        with db_cursor() as cur:
            cur.execute(
                "SELECT sequence_number, entry_hash FROM audit_log "
                "ORDER BY sequence_number DESC LIMIT 1"
            )
            last = cur.fetchone()
            if last:
                next_seq  = last["sequence_number"] + 1
                prev_hash = last["entry_hash"]
            else:
                next_seq  = 1
                prev_hash = GENESIS_HASH

            entry = AuditEntry(
                sequence_number=next_seq,
                prev_entry_hash=prev_hash,
                event_type=event_type,
                source_agent=source_agent,
                record_id=record_id,
                screening_id=screening_id,
                watchlist_version_id=watchlist_version_id,
                payload=payload,
                human_override=human_override,
            )
            entry.entry_hash = entry.compute_hash()

            cur.execute(
                """
                INSERT INTO audit_log (
                    entry_id, sequence_number, prev_entry_hash, event_type,
                    timestamp, source_agent, record_id, screening_id,
                    watchlist_version_id, payload, human_override, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.sequence_number,
                    entry.prev_entry_hash,
                    entry.event_type.value,
                    entry.timestamp.isoformat(),
                    entry.source_agent,
                    entry.record_id,
                    entry.screening_id,
                    entry.watchlist_version_id,
                    json.dumps(entry.payload, default=str),
                    json.dumps(entry.human_override.model_dump(), default=str)
                    if entry.human_override else None,
                    entry.entry_hash,
                ),
            )

        logger.info(
            "[AuditTrailAgent] Appended: entry_id=%s seq=%d event=%s",
            entry.entry_id, entry.sequence_number, event_type.value,
        )
        return entry

    def _row_to_entry(self, row: Dict) -> AuditEntry:
        override = None
        if row.get("human_override"):
            od = json.loads(row["human_override"])
            override = HumanOverride(**od)

        return AuditEntry(
            entry_id=row["entry_id"],
            sequence_number=row["sequence_number"],
            prev_entry_hash=row["prev_entry_hash"],
            event_type=AuditEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            source_agent=row["source_agent"],
            record_id=row.get("record_id"),
            screening_id=row.get("screening_id"),
            watchlist_version_id=row.get("watchlist_version_id"),
            payload=json.loads(row["payload"]),
            human_override=override,
            entry_hash=row["entry_hash"],
        )
