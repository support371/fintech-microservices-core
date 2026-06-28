"""
GovernanceEngine
================
The operational enforcement layer that runs framework controls against
live audit data and produces structured governance reports.

Responsibilities:
  1. Tag audit entries with the framework controls they satisfy (real-time)
  2. Run automated control-assertion sweeps (scheduled or on-demand)
  3. Produce per-framework compliance status reports
  4. Run bias analysis across blocked decisions (COBIT-DSS06.06)
  5. Produce the full reconstruction of any historical decision (GAO-AI-TR.04)
  6. Run the IIA continuous monitoring assertions

Output artefacts:
  - FrameworkControlReport  → per-framework compliance status
  - GovernanceSweepReport   → full cross-framework sweep result
  - BiasAnalysisReport      → block-rate distributions for bias detection
  - DecisionReconstruction  → full audit history for a single screening_id
"""

from __future__ import annotations

import json
import os
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from compliance_agents.audit_trail.agent import AuditTrailAgent
from compliance_agents.governance.frameworks import (
    ALL_CONTROLS,
    CONTROL_MAP,
    Framework,
    GovernanceControl,
    get_controls_for_event,
    get_controls_for_framework,
)
from compliance_agents.shared.models import AuditEntry, AuditEventType
from compliance_agents.shared.storage import fetch_rows, init_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report models (plain dataclasses — not persisted)
# ---------------------------------------------------------------------------

class ControlStatus:
    SATISFIED   = "satisfied"
    PARTIAL     = "partial"
    UNSATISFIED = "unsatisfied"
    NO_DATA     = "no_data"


class FrameworkControlReport:
    def __init__(
        self,
        framework: Framework,
        controls: List[Dict[str, Any]],
        overall_status: str,
        generated_at: datetime,
    ):
        self.framework      = framework
        self.controls       = controls
        self.overall_status = overall_status
        self.generated_at   = generated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework":      self.framework.value,
            "generated_at":   self.generated_at.isoformat(),
            "overall_status": self.overall_status,
            "control_count":  len(self.controls),
            "controls":       self.controls,
        }


class GovernanceSweepReport:
    def __init__(
        self,
        frameworks: List[FrameworkControlReport],
        bias_analysis: Dict[str, Any],
        chain_integrity: Dict[str, Any],
        sweep_period_hours: int,
        generated_at: datetime,
    ):
        self.frameworks         = frameworks
        self.bias_analysis      = bias_analysis
        self.chain_integrity    = chain_integrity
        self.sweep_period_hours = sweep_period_hours
        self.generated_at       = generated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at":       self.generated_at.isoformat(),
            "sweep_period_hours": self.sweep_period_hours,
            "chain_integrity":    self.chain_integrity,
            "bias_analysis":      self.bias_analysis,
            "frameworks":         [f.to_dict() for f in self.frameworks],
        }


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class GovernanceEngine:
    """
    Runs governance control assertions and produces compliance reports
    mapped to COBIT, COSO ERM, GAO AI, and IIA AI frameworks.

    Usage:
        engine = GovernanceEngine()
        report = engine.run_full_sweep(period_hours=24)
        print(json.dumps(report.to_dict(), indent=2))
    """

    def __init__(self) -> None:
        init_db()
        self._audit = AuditTrailAgent()
        logger.info("[GovernanceEngine] Initialised with %d controls across 4 frameworks.", len(ALL_CONTROLS))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_full_sweep(self, period_hours: int = 24) -> GovernanceSweepReport:
        """
        Execute all control assertions across all four frameworks.
        Returns a full GovernanceSweepReport.
        """
        to_dt   = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(hours=period_hours)

        entries = self._audit.query(from_dt=from_dt, to_dt=to_dt, limit=5000)

        framework_reports = []
        for framework in Framework:
            report = self._assess_framework(framework, entries, from_dt, to_dt)
            framework_reports.append(report)

        bias    = self._run_bias_analysis(entries)
        chain   = self._audit.verify_chain_integrity()

        sweep = GovernanceSweepReport(
            frameworks=framework_reports,
            bias_analysis=bias,
            chain_integrity=chain,
            sweep_period_hours=period_hours,
            generated_at=to_dt,
        )

        # Record the sweep itself as an audit event
        self._audit.record_system_event(
            source_agent="GovernanceEngine",
            detail=f"Full governance sweep completed for {period_hours}h window",
            extra={
                "frameworks_assessed": [f.value for f in Framework],
                "entries_analysed":    len(entries),
                "chain_ok":            chain.get("integrity_ok"),
                "bias_flags":          bias.get("flags", []),
            },
        )

        logger.info(
            "[GovernanceEngine] Full sweep complete: %d entries, %d frameworks, chain_ok=%s",
            len(entries), len(Framework), chain.get("integrity_ok"),
        )
        return sweep

    def assess_framework(
        self,
        framework: Framework,
        period_hours: int = 24,
    ) -> FrameworkControlReport:
        """Assess a single framework's controls."""
        to_dt   = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(hours=period_hours)
        entries = self._audit.query(from_dt=from_dt, to_dt=to_dt, limit=5000)
        return self._assess_framework(framework, entries, from_dt, to_dt)

    def tag_entry_with_controls(self, entry: AuditEntry) -> List[str]:
        """
        Return the list of control_ids satisfied by a given audit entry.
        Used to annotate audit query results with framework context.
        """
        matched = get_controls_for_event(entry.event_type.value)
        return [c.control_id for c in matched]

    def reconstruct_decision(self, screening_id: str) -> Dict[str, Any]:
        """
        GAO-AI-TR.04: Reconstruct the full state of the AI system
        at the time of a specific screening decision.
        Returns all audit entries, the model version, prompt version,
        watchlist version, rules triggered, LLM output, and any overrides.
        """
        entries = self._audit.query(screening_id=screening_id, limit=100)
        if not entries:
            return {"error": f"No audit entries found for screening_id={screening_id}"}

        decision_entry = next(
            (e for e in entries if e.event_type in {
                AuditEventType.TRANSACTION_APPROVED,
                AuditEventType.TRANSACTION_FLAGGED,
                AuditEventType.TRANSACTION_BLOCKED,
            }), None
        )
        override_entries = [e for e in entries if e.event_type == AuditEventType.HUMAN_OVERRIDE]

        reconstruction: Dict[str, Any] = {
            "screening_id":     screening_id,
            "reconstructed_at": datetime.now(timezone.utc).isoformat(),
            "audit_entries":    [
                {
                    "entry_id":       e.entry_id,
                    "sequence":       e.sequence_number,
                    "event_type":     e.event_type.value,
                    "timestamp":      e.timestamp.isoformat(),
                    "source_agent":   e.source_agent,
                }
                for e in entries
            ],
            "framework_controls_satisfied": list({
                ctrl_id
                for e in entries
                for ctrl_id in self.tag_entry_with_controls(e)
            }),
        }

        if decision_entry:
            payload = decision_entry.payload
            reconstruction.update({
                "final_decision":       payload.get("final_decision"),
                "final_risk_score":     payload.get("final_risk_score"),
                "decision_rationale":   payload.get("decision_rationale"),
                "watchlist_version_id": decision_entry.watchlist_version_id,
                "rules_triggered": [
                    r for r in payload.get("rule_results", [])
                    if r.get("result") != "pass"
                ],
                "ai_model_state": {
                    "model":          payload.get("llm_analysis", {}).get("model"),
                    "prompt_version": payload.get("llm_analysis", {}).get("prompt_version"),
                    "risk_score":     payload.get("llm_analysis", {}).get("risk_score"),
                    "confidence":     payload.get("llm_analysis", {}).get("confidence"),
                    "flags":          payload.get("llm_analysis", {}).get("flags", []),
                    "narrative":      payload.get("llm_analysis", {}).get("narrative"),
                    "raw_response":   payload.get("llm_analysis", {}).get("raw_response"),
                },
                "transaction_snapshot": payload.get("transaction_snapshot", {}),
            })

        if override_entries:
            reconstruction["human_overrides"] = [
                {
                    "entry_id":    e.entry_id,
                    "timestamp":   e.timestamp.isoformat(),
                    "actor_email": e.payload.get("actor_email"),
                    "action":      e.payload.get("override_action"),
                    "rationale":   e.payload.get("override_rationale"),   # The "why"
                }
                for e in override_entries
            ]

        return reconstruction

    def run_bias_analysis(self, period_hours: int = 168) -> Dict[str, Any]:
        """
        COBIT-DSS06.06 / IIA-AI-ETH.01: Analyse block-rate distributions
        by geography, KYC tier, and currency to surface discriminatory patterns.
        """
        to_dt   = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(hours=period_hours)
        entries = self._audit.query(from_dt=from_dt, to_dt=to_dt, limit=5000)
        return self._run_bias_analysis(entries)

    def get_control(self, control_id: str) -> Optional[Dict[str, Any]]:
        """Return the full definition of a specific control."""
        ctrl = CONTROL_MAP.get(control_id)
        if not ctrl:
            return None
        return {
            "control_id":           ctrl.control_id,
            "framework":            ctrl.framework.value,
            "category":             ctrl.category.value,
            "title":                ctrl.title,
            "description":          ctrl.description,
            "mapped_agent":         ctrl.mapped_agent,
            "mapped_audit_events":  ctrl.mapped_audit_events,
            "implementation_notes": ctrl.implementation_notes,
            "evidence_fields":      ctrl.evidence_fields,
        }

    def list_controls(
        self,
        framework: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all controls, optionally filtered by framework or agent."""
        controls = ALL_CONTROLS
        if framework:
            fw = Framework(framework)
            controls = [c for c in controls if c.framework == fw]
        if agent:
            controls = [c for c in controls if c.mapped_agent == agent]
        return [self.get_control(c.control_id) for c in controls]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assess_framework(
        self,
        framework: Framework,
        entries: List[AuditEntry],
        from_dt: datetime,
        to_dt: datetime,
    ) -> FrameworkControlReport:
        """Assess all controls for a framework against the provided entries."""
        controls = get_controls_for_framework(framework)
        control_results = []
        satisfied_count = 0

        for ctrl in controls:
            # Find entries that relate to this control's mapped events
            relevant = [
                e for e in entries
                if e.event_type.value in ctrl.mapped_audit_events
            ]

            if not relevant:
                status = ControlStatus.NO_DATA
                finding = "No audit entries found in this period for mapped event types."
            else:
                # Run framework-specific assertions
                status, finding = self._run_control_assertion(ctrl, relevant, entries)

            if status == ControlStatus.SATISFIED:
                satisfied_count += 1

            control_results.append({
                "control_id":           ctrl.control_id,
                "title":                ctrl.title,
                "category":             ctrl.category.value,
                "mapped_agent":         ctrl.mapped_agent,
                "status":               status,
                "finding":              finding,
                "evidence_entry_count": len(relevant),
                "evidence_fields":      ctrl.evidence_fields,
            })

        total = len(controls)
        overall = (
            ControlStatus.SATISFIED   if satisfied_count == total and total > 0 else
            ControlStatus.PARTIAL     if satisfied_count > 0 else
            ControlStatus.NO_DATA     if not entries else
            ControlStatus.UNSATISFIED
        )

        return FrameworkControlReport(
            framework=framework,
            controls=control_results,
            overall_status=overall,
            generated_at=datetime.now(timezone.utc),
        )

    def _run_control_assertion(
        self,
        ctrl: GovernanceControl,
        relevant_entries: List[AuditEntry],
        all_entries: List[AuditEntry],
    ):
        """
        Run assertion logic per control.
        Returns (status, finding_string).
        """
        ctrl_id = ctrl.control_id

        # ── COBIT-DSS06.03: Hash-chain integrity ─────────────────────
        if ctrl_id == "COBIT-DSS06.03":
            result = self._audit.verify_chain_integrity()
            ok = result.get("integrity_ok", False)
            return (
                ControlStatus.SATISFIED if ok else ControlStatus.UNSATISFIED,
                f"Chain integrity verified over {result.get('verified_entries', 0)} entries." if ok
                else f"INTEGRITY VIOLATION: {len(result.get('broken_links', []))} broken links detected.",
            )

        # ── COBIT-DSS06.06: Bias — check for anomalous block rates ───
        if ctrl_id == "COBIT-DSS06.06":
            bias = self._run_bias_analysis(all_entries)
            flags = bias.get("flags", [])
            return (
                ControlStatus.SATISFIED if not flags else ControlStatus.PARTIAL,
                f"No bias flags detected. Block distributions within normal range."
                if not flags else
                f"Potential bias indicators: {', '.join(flags)}. Manual review recommended.",
            )

        # ── GAO-AI-DI.02: Every ingested record has raw_checksum ─────
        if ctrl_id == "GAO-AI-DI.02":
            entries_with_checksum = [
                e for e in relevant_entries
                if e.payload.get("raw_checksum") or e.payload.get("checksum")
            ]
            ratio = len(entries_with_checksum) / len(relevant_entries) if relevant_entries else 0
            return (
                ControlStatus.SATISFIED if ratio == 1.0 else ControlStatus.PARTIAL,
                f"{len(entries_with_checksum)}/{len(relevant_entries)} ingestion entries have raw_checksum ({ratio:.0%}).",
            )

        # ── GAO-AI-ACC.01: Every decision has rationale ───────────────
        if ctrl_id == "GAO-AI-ACC.01":
            _is_synthetic = lambda e: (
                "seed" in str(e.payload.get("detail", "")).lower()
                or "seed" in str(e.payload.get("flag_reason", "")).lower()
                or "synthetic" in str(e.payload.get("detail", "")).lower()
            )
            decision_entries = [
                e for e in relevant_entries
                if e.event_type.value in {"transaction_approved", "transaction_flagged", "transaction_blocked"}
                and not _is_synthetic(e)
            ]
            with_rationale = [e for e in decision_entries if e.payload.get("decision_rationale")]
            if not decision_entries:
                return ControlStatus.SATISFIED, "No real (non-seed) decision entries in period — control satisfied by design."
            ratio = len(with_rationale) / len(decision_entries)
            return (
                ControlStatus.SATISFIED if ratio == 1.0 else ControlStatus.PARTIAL,
                f"{len(with_rationale)}/{len(decision_entries)} decisions have documented rationale ({ratio:.0%}).",
            )

        # ── IIA-AI-IND.03: Audit independence — no update/delete events
        if ctrl_id == "IIA-AI-IND.03":
            # If audit entries exist and chain is intact, independence is maintained
            result = self._audit.verify_chain_integrity()
            ok = result.get("integrity_ok", False)
            return (
                ControlStatus.SATISFIED if ok else ControlStatus.UNSATISFIED,
                "Audit trail independence maintained — no mutations detected."
                if ok else
                "INDEPENDENCE VIOLATION: Audit chain broken. Possible unauthorised mutation.",
            )

        # ── IIA-AI-CM.04: Continuous monitoring — check override rate ─
        if ctrl_id == "IIA-AI-CM.04":
            total_decisions = sum(
                1 for e in all_entries
                if e.event_type.value in {"transaction_approved", "transaction_flagged", "transaction_blocked"}
            )
            overrides = sum(1 for e in all_entries if e.event_type == AuditEventType.HUMAN_OVERRIDE)
            if total_decisions == 0:
                return ControlStatus.NO_DATA, "No decisions in period."
            rate = overrides / total_decisions
            threshold = float(os.environ.get("IIA_OVERRIDE_RATE_THRESHOLD", "0.20"))  # configurable; default 20%
            return (
                ControlStatus.SATISFIED if rate <= threshold else ControlStatus.PARTIAL,
                f"Override rate: {rate:.1%} ({overrides}/{total_decisions} decisions). "
                + ("Within acceptable range." if rate <= threshold
                   else f"Exceeds {threshold:.0%} threshold — review recommended."),
            )

        # ── COSO-RC.05: Human overrides have documented rationale ─────
        if ctrl_id == "COSO-RC.05":
            override_entries = [e for e in all_entries if e.event_type == AuditEventType.HUMAN_OVERRIDE]
            with_rationale = [
                e for e in override_entries
                if e.payload.get("override_rationale") and len(e.payload.get("override_rationale", "")) >= 10
            ]
            if not override_entries:
                return ControlStatus.SATISFIED, "No human overrides in period."
            ratio = len(with_rationale) / len(override_entries)
            return (
                ControlStatus.SATISFIED if ratio == 1.0 else ControlStatus.UNSATISFIED,
                f"{len(with_rationale)}/{len(override_entries)} overrides have documented rationale ({ratio:.0%}).",
            )

        # ── Default: evidence-based pass if relevant entries exist ────
        return (
            ControlStatus.SATISFIED if relevant_entries else ControlStatus.NO_DATA,
            f"{len(relevant_entries)} audit entries provide evidence for this control."
            if relevant_entries else
            "No audit entries found for mapped event types in this period.",
        )

    def _run_bias_analysis(self, entries: List[AuditEntry]) -> Dict[str, Any]:
        """
        Analyse block-rate distributions by geography, KYC tier, and currency.
        Flags anomalous patterns that may indicate algorithmic bias.
        """
        blocked_entries = [
            e for e in entries
            if e.event_type == AuditEventType.TRANSACTION_BLOCKED
        ]
        total_decisions = sum(
            1 for e in entries
            if e.event_type.value in {"transaction_approved", "transaction_flagged", "transaction_blocked"}
        )

        # Block rate by country
        country_totals: Dict[str, int]  = defaultdict(int)
        country_blocks: Dict[str, int]  = defaultdict(int)
        kyc_totals: Dict[str, int]      = defaultdict(int)
        kyc_blocks: Dict[str, int]      = defaultdict(int)
        currency_totals: Dict[str, int] = defaultdict(int)
        currency_blocks: Dict[str, int] = defaultdict(int)

        for e in entries:
            if e.event_type.value not in {"transaction_approved", "transaction_flagged", "transaction_blocked"}:
                continue
            snap = e.payload.get("transaction_snapshot", {})
            country  = snap.get("country_code") or snap.get("country") or "UNKNOWN"
            kyc      = str(snap.get("kyc_tier") or snap.get("kyc_status") or "UNKNOWN")
            currency = snap.get("currency") or snap.get("fiat_currency") or "UNKNOWN"

            country_totals[country]   += 1
            kyc_totals[kyc]           += 1
            currency_totals[currency] += 1

            if e.event_type == AuditEventType.TRANSACTION_BLOCKED:
                country_blocks[country]   += 1
                kyc_blocks[kyc]           += 1
                currency_blocks[currency] += 1

        def block_rates(totals, blocks):
            return {
                k: {"total": totals[k], "blocked": blocks.get(k, 0),
                    "rate": round(blocks.get(k, 0) / totals[k], 3) if totals[k] else 0}
                for k in totals
            }

        country_rates  = block_rates(country_totals, country_blocks)
        kyc_rates      = block_rates(kyc_totals, kyc_blocks)
        currency_rates = block_rates(currency_totals, currency_blocks)

        # Flag anomalies: any non-restricted country with >50% block rate (>5 txns)
        flags = []
        restricted = {"CU", "IR", "KP", "SY", "RU", "BY", "MM", "SD", "ZW"}
        for country, data in country_rates.items():
            if country not in restricted and data["total"] >= 5 and data["rate"] > 0.5:
                flags.append(f"High block rate for non-restricted country {country}: {data['rate']:.0%}")

        for kyc, data in kyc_rates.items():
            if data["total"] >= 5 and data["rate"] > 0.7 and kyc not in ("UNKNOWN", "0"):
                flags.append(f"High block rate for KYC tier {kyc}: {data['rate']:.0%}")

        return {
            "total_decisions":  total_decisions,
            "total_blocked":    len(blocked_entries),
            "overall_block_rate": round(len(blocked_entries) / total_decisions, 3) if total_decisions else 0,
            "by_country":       country_rates,
            "by_kyc_tier":      kyc_rates,
            "by_currency":      currency_rates,
            "flags":            flags,
            "analysed_at":      datetime.now(timezone.utc).isoformat(),
        }
