"""
NexusComplianceOrchestrator
============================
Top-level orchestrator that wires all four agents into a single
end-to-end compliance pipeline.

Full pipeline for a single record:
  1. DataIngestionAgent  → normalise, deduplicate, version
  2. AuditTrailAgent     → record ingestion event
  3. ScreeningAgent      → rules + LLM → ScreeningResult
  4. AuditTrailAgent     → record screening decision (with full context)
  5. ReportingAgent      → auto-generate SAR if risk is HIGH/CRITICAL

Human Override flow:
  analyst calls orchestrator.apply_human_override(...)
  → validates rationale is present and non-trivial
  → AuditTrailAgent records override with documented "why"
  → returns updated AuditEntry

This file is the integration point for the existing Nexus FastAPI services.
card_platform_service and converter_service should call process_transaction()
in place of (or in addition to) their existing compliance checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from compliance_agents.audit_trail.agent import AuditTrailAgent
from compliance_agents.data_ingestion.agent import DataIngestionAgent
from compliance_agents.reporting.agent import ReportingAgent
from compliance_agents.screening.agent import ScreeningAgent
from compliance_agents.shared.models import (
    AuditEntry,
    ComplianceReport,
    DataStreamType,
    IngestedRecord,
    OverrideAction,
    RiskScore,
    SARReport,
    ScreeningResult,
    ScreeningRuleResult,
    WatchlistVersion,
)

logger = logging.getLogger(__name__)

AUTO_SAR_RISK_THRESHOLD = {RiskScore.HIGH, RiskScore.CRITICAL}


class NexusComplianceOrchestrator:
    """
    Single entry point for all compliance operations.

    Instantiate once and reuse (agents hold DB connections).
    """

    def __init__(self) -> None:
        self._ingestion  = DataIngestionAgent()
        self._audit      = AuditTrailAgent()
        self._screening  = ScreeningAgent()
        self._reporting  = ReportingAgent()
        logger.info("[Orchestrator] NexusComplianceOrchestrator ready.")

    # ------------------------------------------------------------------
    # Primary pipeline
    # ------------------------------------------------------------------

    def process_transaction(
        self,
        raw_payload: Dict[str, Any],
        source: str,
        stream_type: str | DataStreamType = DataStreamType.TRANSACTION_LOG,
        watchlist_entries: Optional[List[str]] = None,
        force_llm: bool = False,
    ) -> Dict[str, Any]:
        """
        Full compliance pipeline for a single transaction or event.

        Returns a summary dict suitable for returning directly from a FastAPI endpoint.
        """
        stream_type = DataStreamType(stream_type)

        # Step 1: Ingest
        record = self._ingestion.ingest(
            stream_type=stream_type,
            source=source,
            raw=raw_payload,
        )

        # Step 2: Audit ingestion
        ingestion_entry = self._audit.record_ingestion(record)

        if record.is_duplicate:
            return {
                "status":     "duplicate",
                "record_id":  record.record_id,
                "duplicate_of": record.duplicate_of,
                "audit_entry_id": ingestion_entry.entry_id,
                "message":    "Record already processed — idempotent response.",
            }

        # Step 3: Screen
        screening_result = self._screening.screen(
            record=record,
            watchlist_entries=watchlist_entries,
            force_llm=force_llm,
        )

        # Step 4: Audit screening decision
        decision_entry = self._audit.record_screening_decision(record, screening_result)

        # Step 5: Auto-generate SAR for high-risk results
        sar: Optional[SARReport] = None
        if screening_result.final_risk_score in AUTO_SAR_RISK_THRESHOLD:
            user_id = record.payload.get("user_id", "unknown")
            try:
                sar = self._reporting.generate_sar(
                    subject_user_id=user_id,
                    from_dt=record.ingested_at,
                    to_dt=datetime.now(timezone.utc),
                )
                logger.info(
                    f"[Orchestrator] Auto-SAR generated: sar_id={sar.sar_id} "
                    f"user={user_id} risk={screening_result.final_risk_score.value}"
                )
            except Exception as exc:
                logger.error(f"[Orchestrator] Auto-SAR generation failed: {exc}")

        response: Dict[str, Any] = {
            "status":             "processed",
            "record_id":          record.record_id,
            "version_id":         record.version_id,
            "screening_id":       screening_result.screening_id,
            "watchlist_version":  screening_result.watchlist_version_id,
            "final_decision":     screening_result.final_decision.value,
            "risk_score":         screening_result.final_risk_score.value,
            "decision_rationale": screening_result.decision_rationale,
            "audit_entry_id":     decision_entry.entry_id,
            "rules_triggered": [
                {"rule_id": r.rule_id, "rule": r.rule_name, "result": r.result.value, "detail": r.detail}
                for r in screening_result.rule_results
                if r.result != ScreeningRuleResult.PASS
            ],
        }

        if screening_result.llm_analysis:
            response["llm_summary"] = {
                "risk_score": screening_result.llm_analysis.risk_score.value,
                "confidence": screening_result.llm_analysis.confidence,
                "flags":      screening_result.llm_analysis.flags,
                "narrative":  screening_result.llm_analysis.narrative,
            }

        if sar:
            response["sar_auto_generated"] = {
                "sar_id": sar.sar_id,
                "status": sar.status,
            }

        return response

    def process_user_profile(
        self,
        user_payload: Dict[str, Any],
        source: str = "card_platform_service",
    ) -> Dict[str, Any]:
        """Convenience wrapper for user profile / KYC update ingestion."""
        return self.process_transaction(
            raw_payload=user_payload,
            source=source,
            stream_type=DataStreamType.USER_PROFILE,
            force_llm=True,   # Always run LLM on user profiles
        )

    def process_watchlist_update(
        self,
        list_name: str,
        raw_content: bytes,
        record_count: int,
        effective_date: datetime,
        source_url: Optional[str] = None,
    ) -> WatchlistVersion:
        """Ingest a new version of a regulatory watchlist."""
        wl = self._ingestion.ingest_watchlist(
            list_name=list_name,
            raw_content=raw_content,
            record_count=record_count,
            effective_date=effective_date,
            source_url=source_url,
        )
        self._audit.record_system_event(
            source_agent="DataIngestionAgent",
            detail=f"Watchlist updated: {list_name}",
            extra={
                "watchlist_version_id": wl.watchlist_version_id,
                "list_name":    wl.list_name,
                "record_count": wl.record_count,
                "checksum":     wl.checksum,
                "effective_date": wl.effective_date.isoformat(),
            },
        )
        return wl

    # ------------------------------------------------------------------
    # Human override flow
    # ------------------------------------------------------------------

    def apply_human_override(
        self,
        screening_id: str,
        actor_id: str,
        actor_email: str,
        action: str,
        rationale: str,
    ) -> AuditEntry:
        """
        Apply and permanently record a human override of a screening decision.

        Rationale is MANDATORY. Minimum 10 characters.
        This entry is immutable once written — it is the permanent record
        of WHY the override was made, protecting the firm from audit exposure.
        """
        if not rationale or len(rationale.strip()) < 10:
            raise ValueError(
                "Human override rationale is required and must be at least 10 characters. "
                "Document the specific reason for this override."
            )

        # Retrieve the original screening result
        rows = __import__(
            "compliance_agents.shared.storage", fromlist=["fetch_rows"]
        ).fetch_rows(
            "screening_results",
            where="screening_id = ?",
            params=[screening_id],
            limit=1,
        )
        if not rows:
            raise ValueError(f"No screening result found for screening_id={screening_id}")

        import json as _json
        from compliance_agents.shared.models import ScreeningRuleResult as SRR
        sr_row = rows[0]
        # Reconstruct a minimal ScreeningResult for the audit entry
        from compliance_agents.shared.models import ScreeningResult
        from compliance_agents.shared.models import RiskScore

        screening_result = ScreeningResult(
            screening_id=sr_row["screening_id"],
            record_id=sr_row["record_id"],
            watchlist_version_id=sr_row["watchlist_version_id"],
            screened_at=datetime.fromisoformat(sr_row["screened_at"]),
            rule_results=[],   # Not needed for override record
            final_risk_score=RiskScore(sr_row["final_risk_score"]),
            final_decision=SRR(sr_row["final_decision"]),
            decision_rationale=sr_row["decision_rationale"],
        )

        entry = self._audit.record_human_override(
            screening_result=screening_result,
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            rationale=rationale,
        )

        logger.info(
            f"[Orchestrator] Human override recorded: entry_id={entry.entry_id} "
            f"screening={screening_id} actor={actor_email} action={action}"
        )
        return entry

    # ------------------------------------------------------------------
    # Reporting shortcuts
    # ------------------------------------------------------------------

    def generate_sar(
        self,
        subject_user_id: str,
        hours_back: int = 72,
    ) -> SARReport:
        """Generate a SAR covering the last N hours for a user."""
        to_dt = datetime.now(timezone.utc)
        from_dt = to_dt - __import__("datetime").timedelta(hours=hours_back)
        return self._reporting.generate_sar(
            subject_user_id=subject_user_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    def generate_compliance_report(self, period_hours: int = 24) -> ComplianceReport:
        return self._reporting.generate_compliance_report(period_hours=period_hours)

    def verify_audit_integrity(self) -> Dict[str, Any]:
        return self._audit.verify_chain_integrity()

    def query_audit_trail(self, **kwargs) -> List[AuditEntry]:
        return self._audit.query(**kwargs)
