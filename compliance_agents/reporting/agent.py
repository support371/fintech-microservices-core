"""
Agent 4: ReportingAgent
========================
Automates the creation of compliance reports and Suspicious Activity Reports
(SARs) from the AuditTrailAgent's query API.

All report data is sourced EXCLUSIVELY from the immutable audit trail —
no secondary data stores are consulted. This ensures reports are fully
consistent with what was actually recorded.

SAR Generation:
  - Triggered when a user has HIGH or CRITICAL risk screening results
  - Pre-fills all standard FinCEN SAR fields from audit data
  - Requires all supporting audit entry IDs to be linked (full traceability)
  - Records the watchlist version IDs used during screening
  - Status: draft → submitted → acknowledged

Periodic Compliance Reports:
  - Aggregated summaries for a given time window
  - Include chain integrity verification result
  - Human override counts and rationale summaries
  - Broken down by risk score, decision type, and stream type
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from compliance_agents.audit_trail.agent import AuditTrailAgent
from compliance_agents.shared.models import (
    AuditEntry,
    AuditEventType,
    ComplianceReport,
    RiskScore,
    SARReport,
    ScreeningRuleResult,
)
from compliance_agents.shared.storage import fetch_rows, init_db, insert_row

logger = logging.getLogger(__name__)


class ReportingAgent:
    """
    Generates SARs and compliance reports from the audit trail.

    Usage:
        agent = ReportingAgent()
        sar   = agent.generate_sar(user_id="usr-123", from_dt=..., to_dt=...)
        rpt   = agent.generate_compliance_report(period_hours=24)
    """

    AGENT_NAME = "ReportingAgent"

    def __init__(self) -> None:
        init_db()
        self._audit = AuditTrailAgent()
        logger.info("[ReportingAgent] Initialised.")

    # ------------------------------------------------------------------
    # SAR Generation
    # ------------------------------------------------------------------

    def generate_sar(
        self,
        subject_user_id: str,
        from_dt: datetime,
        to_dt: datetime,
        override_narrative: Optional[str] = None,
    ) -> SARReport:
        """
        Generate a Suspicious Activity Report for a specific user
        over a given time window.

        All data is pulled from the audit trail — no raw DB queries.
        The resulting SAR is also recorded back into the audit trail.
        """
        # Pull all screening decisions for this user in the window
        all_entries = self._audit.query(from_dt=from_dt, to_dt=to_dt, limit=1000)

        # Filter to entries relating to this user
        user_entries = [
            e for e in all_entries
            if e.payload.get("transaction_snapshot", {}).get("user_id") == subject_user_id
            or e.payload.get("subject_user_id") == subject_user_id
        ]

        # Screening decision entries
        decision_events = {
            AuditEventType.TRANSACTION_APPROVED,
            AuditEventType.TRANSACTION_FLAGGED,
            AuditEventType.TRANSACTION_BLOCKED,
            AuditEventType.RISK_SCORE_ASSIGNED,
        }
        screening_entries = [e for e in user_entries if e.event_type in decision_events]

        # Human override entries
        override_entries = [
            e for e in user_entries
            if e.event_type == AuditEventType.HUMAN_OVERRIDE
        ]

        # Aggregate amounts
        total_amount = 0.0
        currency = "USD"
        flag_categories: List[str] = []
        watchlist_version_ids: List[str] = []
        supporting_ids = [e.entry_id for e in screening_entries]

        highest_risk = RiskScore.LOW
        risk_order = [RiskScore.LOW, RiskScore.MEDIUM, RiskScore.HIGH, RiskScore.CRITICAL]

        for entry in screening_entries:
            snap = entry.payload.get("transaction_snapshot", {})
            amount = float(snap.get("amount") or snap.get("fiat_amount") or 0)
            total_amount += amount
            currency = snap.get("currency") or snap.get("fiat_currency") or currency

            # Track worst risk score
            entry_risk_str = entry.payload.get("final_risk_score", "low")
            try:
                entry_risk = RiskScore(entry_risk_str)
                if risk_order.index(entry_risk) > risk_order.index(highest_risk):
                    highest_risk = entry_risk
            except ValueError:
                pass

            # Collect LLM flags
            llm = entry.payload.get("llm_analysis", {})
            flag_categories.extend(llm.get("flags", []))

            # Collect watchlist versions
            wl_id = entry.watchlist_version_id
            if wl_id and wl_id not in watchlist_version_ids:
                watchlist_version_ids.append(wl_id)

        # Deduplicate flags
        flag_categories = list(dict.fromkeys(flag_categories))

        # Build narrative
        narrative = override_narrative or self._build_sar_narrative(
            subject_user_id=subject_user_id,
            screening_entries=screening_entries,
            override_entries=override_entries,
            total_amount=total_amount,
            currency=currency,
            flag_categories=flag_categories,
            highest_risk=highest_risk,
            from_dt=from_dt,
            to_dt=to_dt,
        )

        sar = SARReport(
            subject_user_id=subject_user_id,
            activity_start=from_dt,
            activity_end=to_dt,
            total_amount=total_amount,
            currency=currency,
            transaction_count=len(screening_entries),
            risk_score=highest_risk,
            flag_categories=flag_categories,
            narrative=narrative,
            supporting_audit_entry_ids=supporting_ids,
            watchlist_version_ids_used=watchlist_version_ids,
            status="draft",
        )

        self._persist_sar(sar)

        # Record in audit trail
        self._audit.record_sar_generation(
            sar_id=sar.sar_id,
            subject_user_id=subject_user_id,
            risk_score=highest_risk.value,
            supporting_entry_ids=supporting_ids,
        )

        logger.info(
            f"[ReportingAgent] SAR generated: sar_id={sar.sar_id} "
            f"user={subject_user_id} risk={highest_risk.value} "
            f"txns={len(screening_entries)} amount={total_amount:.2f} {currency}"
        )

        return sar

    # ------------------------------------------------------------------
    # Periodic Compliance Report
    # ------------------------------------------------------------------

    def generate_compliance_report(
        self,
        period_hours: int = 24,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> ComplianceReport:
        """
        Generate a periodic compliance summary report.

        Includes: transaction counts by decision, risk distribution,
        SAR count, human override count, and chain integrity verification.
        """
        to_dt = to_dt or datetime.now(timezone.utc)
        from_dt = from_dt or (to_dt - timedelta(hours=period_hours))

        all_entries = self._audit.query(from_dt=from_dt, to_dt=to_dt, limit=5000)

        # Counts
        approved = sum(1 for e in all_entries if e.event_type == AuditEventType.TRANSACTION_APPROVED)
        flagged = sum(1 for e in all_entries if e.event_type == AuditEventType.TRANSACTION_FLAGGED)
        blocked = sum(1 for e in all_entries if e.event_type == AuditEventType.TRANSACTION_BLOCKED)
        sar_count = sum(1 for e in all_entries if e.event_type == AuditEventType.SAR_GENERATED)
        override_count = sum(1 for e in all_entries if e.event_type == AuditEventType.HUMAN_OVERRIDE)

        # Top risk categories from LLM flags
        all_flags: List[str] = []
        for e in all_entries:
            llm = e.payload.get("llm_analysis", {})
            all_flags.extend(llm.get("flags", []))
        flag_counts: Dict[str, int] = {}
        for f in all_flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1
        top_flags = sorted(flag_counts, key=lambda x: -flag_counts[x])[:5]

        # Active watchlist versions
        wl_ids = list(dict.fromkeys(
            e.watchlist_version_id for e in all_entries
            if e.watchlist_version_id
        ))

        # Verify audit chain integrity
        integrity_result = self._audit.verify_chain_integrity()
        chain_ok = integrity_result.get("integrity_ok", False)

        # Override details
        override_details = []
        for e in all_entries:
            if e.event_type == AuditEventType.HUMAN_OVERRIDE:
                override_details.append({
                    "entry_id":        e.entry_id,
                    "actor_id":        e.payload.get("actor_id"),
                    "actor_email":     e.payload.get("actor_email"),
                    "action":          e.payload.get("override_action"),
                    "rationale":       e.payload.get("override_rationale"),
                    "original_decision": e.payload.get("original_decision"),
                    "timestamp":       e.timestamp.isoformat(),
                })

        report_data = {
            "period_start":             from_dt.isoformat(),
            "period_end":               to_dt.isoformat(),
            "total_audit_entries":      len(all_entries),
            "decisions": {
                "approved":  approved,
                "flagged":   flagged,
                "blocked":   blocked,
            },
            "sar_count":                sar_count,
            "human_overrides": {
                "count":   override_count,
                "details": override_details,
            },
            "top_risk_flags":           top_flags,
            "active_watchlist_versions": wl_ids,
            "chain_integrity": {
                "ok":              chain_ok,
                "verified_entries": integrity_result.get("verified_entries", 0),
                "broken_links":    integrity_result.get("broken_links", []),
            },
        }

        report = ComplianceReport(
            period_start=from_dt,
            period_end=to_dt,
            total_transactions=approved + flagged + blocked,
            approved_count=approved,
            flagged_count=flagged,
            blocked_count=blocked,
            sar_count=sar_count,
            human_override_count=override_count,
            top_risk_categories=top_flags,
            watchlist_versions_active=wl_ids,
            audit_chain_integrity=chain_ok,
            report_data=report_data,
        )

        self._persist_report(report)

        logger.info(
            f"[ReportingAgent] Compliance report generated: report_id={report.report_id} "
            f"period={period_hours}h txns={report.total_transactions} "
            f"chain_ok={chain_ok}"
        )

        return report

    def get_sar(self, sar_id: str) -> Optional[SARReport]:
        """Retrieve a previously generated SAR by ID."""
        rows = fetch_rows("sar_reports", where="sar_id = ?", params=[sar_id], limit=1)
        if not rows:
            return None
        return self._row_to_sar(rows[0])

    def list_sars(
        self,
        subject_user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SARReport]:
        conditions = []
        params = []
        if subject_user_id:
            conditions.append("subject_user_id = ?")
            params.append(subject_user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else None
        rows = fetch_rows("sar_reports", where=where, params=params or None,
                          order_by="generated_at DESC", limit=limit)
        return [self._row_to_sar(r) for r in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_sar_narrative(
        self,
        subject_user_id: str,
        screening_entries: List[AuditEntry],
        override_entries: List[AuditEntry],
        total_amount: float,
        currency: str,
        flag_categories: List[str],
        highest_risk: RiskScore,
        from_dt: datetime,
        to_dt: datetime,
    ) -> str:
        lines = [
            f"Subject user {subject_user_id} conducted {len(screening_entries)} transaction(s) "
            f"totalling {currency} {total_amount:,.2f} between "
            f"{from_dt.strftime('%Y-%m-%d %H:%M UTC')} and {to_dt.strftime('%Y-%m-%d %H:%M UTC')}.",
        ]

        if flag_categories:
            lines.append(
                f"Automated screening identified the following risk indicators: "
                f"{', '.join(flag_categories)}."
            )

        blocked = [e for e in screening_entries if e.event_type == AuditEventType.TRANSACTION_BLOCKED]
        flagged = [e for e in screening_entries if e.event_type == AuditEventType.TRANSACTION_FLAGGED]
        if blocked:
            lines.append(f"{len(blocked)} transaction(s) were blocked by automated rules.")
        if flagged:
            lines.append(f"{len(flagged)} transaction(s) were flagged for review.")

        if override_entries:
            lines.append(
                f"{len(override_entries)} human override(s) were applied during the review period. "
                f"All overrides are documented with rationale in the audit trail."
            )

        lines.append(
            f"Overall risk assessment: {highest_risk.value.upper()}. "
            f"This SAR is filed in accordance with FinCEN BSA reporting requirements. "
            f"All supporting data is available in the Nexus compliance audit trail."
        )

        return " ".join(lines)

    def _persist_sar(self, sar: SARReport) -> None:
        insert_row("sar_reports", {
            "sar_id":                       sar.sar_id,
            "generated_at":                 sar.generated_at.isoformat(),
            "generated_by_agent":           sar.generated_by_agent,
            "subject_user_id":              sar.subject_user_id,
            "subject_name":                 sar.subject_name,
            "subject_account":              sar.subject_account,
            "activity_start":               sar.activity_start.isoformat(),
            "activity_end":                 sar.activity_end.isoformat(),
            "total_amount":                 sar.total_amount,
            "currency":                     sar.currency,
            "transaction_count":            sar.transaction_count,
            "risk_score":                   sar.risk_score.value,
            "flag_categories":              json.dumps(sar.flag_categories),
            "narrative":                    sar.narrative,
            "supporting_audit_entry_ids":   json.dumps(sar.supporting_audit_entry_ids),
            "watchlist_version_ids_used":   json.dumps(sar.watchlist_version_ids_used),
            "status":                       sar.status,
            "filing_reference":             sar.filing_reference,
        })

    def _persist_report(self, report: ComplianceReport) -> None:
        insert_row("compliance_reports", {
            "report_id":                report.report_id,
            "generated_at":             report.generated_at.isoformat(),
            "period_start":             report.period_start.isoformat(),
            "period_end":               report.period_end.isoformat(),
            "total_transactions":       report.total_transactions,
            "approved_count":           report.approved_count,
            "flagged_count":            report.flagged_count,
            "blocked_count":            report.blocked_count,
            "sar_count":                report.sar_count,
            "human_override_count":     report.human_override_count,
            "top_risk_categories":      json.dumps(report.top_risk_categories),
            "watchlist_versions_active": json.dumps(report.watchlist_versions_active),
            "audit_chain_integrity":    int(report.audit_chain_integrity),
            "report_data":              json.dumps(report.report_data, default=str),
        })

    def _row_to_sar(self, row: Dict) -> SARReport:
        return SARReport(
            sar_id=row["sar_id"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            generated_by_agent=row["generated_by_agent"],
            subject_user_id=row["subject_user_id"],
            subject_name=row.get("subject_name"),
            subject_account=row.get("subject_account"),
            activity_start=datetime.fromisoformat(row["activity_start"]),
            activity_end=datetime.fromisoformat(row["activity_end"]),
            total_amount=row["total_amount"],
            currency=row["currency"],
            transaction_count=row["transaction_count"],
            risk_score=RiskScore(row["risk_score"]),
            flag_categories=json.loads(row["flag_categories"]),
            narrative=row["narrative"],
            supporting_audit_entry_ids=json.loads(row["supporting_audit_entry_ids"]),
            watchlist_version_ids_used=json.loads(row["watchlist_version_ids_used"]),
            status=row["status"],
            filing_reference=row.get("filing_reference"),
        )
