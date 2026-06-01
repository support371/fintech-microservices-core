"""
Agent 2: ScreeningAgent (with LLM integration)
================================================
Combines rule-based screening with Claude LLM analysis to produce
a final risk score and decision for each IngestedRecord.

Pipeline:
  IngestedRecord → Rule Engine (7 rules) → LLM analysis (Claude)
                → aggregate decision → ScreeningResult
                → emit AuditEntry via AuditTrailAgent

CRITICAL: Every ScreeningResult records the watchlist_version_id that
was active at screening time. This is a hard regulatory requirement.

LLM Role:
  - Analyses the full normalised payload + all rule results
  - Identifies qualitative / contextual red flags that rules miss
  - Assigns an independent risk score (low/medium/high/critical)
  - Provides a plain-English narrative for the audit record
  - Its raw response is stored verbatim in the audit trail
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import anthropic

from compliance_agents.data_ingestion.agent import DataIngestionAgent
from compliance_agents.shared.models import (
    AuditEventType,
    IngestedRecord,
    LLMAnalysis,
    RiskScore,
    ScreeningResult,
    ScreeningRuleResult,
    WatchlistVersion,
)
from compliance_agents.shared.storage import fetch_rows, init_db, insert_row
from compliance_agents.screening.rules import RuleEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk score mapping
# ---------------------------------------------------------------------------

RULE_DECISION_TO_RISK: Dict[ScreeningRuleResult, RiskScore] = {
    ScreeningRuleResult.PASS:  RiskScore.LOW,
    ScreeningRuleResult.FLAG:  RiskScore.MEDIUM,
    ScreeningRuleResult.BLOCK: RiskScore.HIGH,
}

LLM_PROMPT_VERSION = "v1.2.0"

LLM_SYSTEM_PROMPT = """You are a senior AML (Anti-Money Laundering) compliance analyst for Alliance Trust Realty's Nexus fintech platform. Your job is to review financial transaction data and rule-based screening results, then provide an expert qualitative risk assessment.

You must respond with ONLY valid JSON matching this exact schema:
{
  "risk_score": "low" | "medium" | "high" | "critical",
  "confidence": <float 0.0-1.0>,
  "flags": ["<flag1>", "<flag2>"],
  "narrative": "<plain English explanation for auditors, 2-4 sentences>"
}

Guidelines:
- "low": Transaction appears legitimate, no unusual patterns
- "medium": Some indicators warrant human review but not immediate blocking
- "high": Strong indicators of suspicious activity, escalate immediately
- "critical": Clear indicators of fraud, money laundering, or sanctions violation

Common flags to use: structuring, velocity_spike, geographic_risk, watchlist_proximity, kyc_mismatch, round_amount_pattern, unusual_hours, beneficiary_risk, layering_pattern, smurfing

Be concise. The narrative will appear in regulatory audit trails and SAR filings.
"""


class ScreeningAgent:
    """
    Modular screening system combining rule-based logic with LLM analysis.

    Usage:
        agent = ScreeningAgent()
        result = agent.screen(record, watchlist_version_id="wl-abc123")
    """

    AGENT_NAME = "ScreeningAgent"

    def __init__(self) -> None:
        init_db()
        self._rule_engine = RuleEngine()
        self._ingestion_agent = DataIngestionAgent()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._llm_client = anthropic.Anthropic(api_key=api_key) if api_key else None
        if not self._llm_client:
            logger.warning(
                "[ScreeningAgent] ANTHROPIC_API_KEY not set — LLM analysis disabled. "
                "Rule-based screening will still run."
            )
        logger.info("[ScreeningAgent] Initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def screen(
        self,
        record: IngestedRecord,
        watchlist_version_id: Optional[str] = None,
        watchlist_entries: Optional[List[str]] = None,
        force_llm: bool = False,
    ) -> ScreeningResult:
        """
        Screen a single IngestedRecord.

        Args:
            record: The normalised record from DataIngestionAgent.
            watchlist_version_id: ID of the watchlist version to reference.
                                   Falls back to most recent OFAC_SDN version.
            watchlist_entries: Optional list of names from the active watchlist.
            force_llm: Always run LLM even for low-rule-risk records.

        Returns:
            ScreeningResult with full rule + LLM context.
        """
        # Resolve watchlist version
        wl_version_id = watchlist_version_id or self._get_active_watchlist_id()

        user_id = record.payload.get("user_id")

        # ── Step 1: Rule-based screening ─────────────────────────────────
        rule_results = self._rule_engine.evaluate(
            payload=record.payload,
            user_id=user_id,
            watchlist_entries=watchlist_entries or [],
        )
        rule_decision = self._rule_engine.aggregate_decision(rule_results)
        rule_risk = RULE_DECISION_TO_RISK[rule_decision]

        logger.info(
            f"[ScreeningAgent] Rules complete for record={record.record_id}: "
            f"decision={rule_decision.value} risk={rule_risk.value}"
        )

        # ── Step 2: LLM analysis ─────────────────────────────────────────
        # Run LLM when: forced, or rule decision is not a clean PASS,
        # or the stream type is a user_profile (always do behavioural analysis)
        should_run_llm = (
            force_llm
            or rule_decision != ScreeningRuleResult.PASS
            or record.stream_type.value == "user_profile"
        )

        llm_analysis: Optional[LLMAnalysis] = None
        if should_run_llm and self._llm_client:
            llm_analysis = self._run_llm_analysis(record, rule_results, rule_decision)

        # ── Step 3: Aggregate final decision ─────────────────────────────
        final_risk, final_decision, rationale = self._aggregate_final(
            rule_decision, rule_risk, llm_analysis, rule_results
        )

        result = ScreeningResult(
            record_id=record.record_id,
            watchlist_version_id=wl_version_id,
            rule_results=rule_results,
            llm_analysis=llm_analysis,
            final_risk_score=final_risk,
            final_decision=final_decision,
            decision_rationale=rationale,
        )

        self._persist(result)

        logger.info(
            f"[ScreeningAgent] Screening complete: screening_id={result.screening_id} "
            f"final={final_decision.value} risk={final_risk.value} "
            f"watchlist_version={wl_version_id}"
        )

        return result

    def screen_batch(
        self,
        records: List[IngestedRecord],
        watchlist_version_id: Optional[str] = None,
        watchlist_entries: Optional[List[str]] = None,
    ) -> List[ScreeningResult]:
        """Screen a list of records, skipping duplicates."""
        results = []
        for record in records:
            if record.is_duplicate:
                logger.debug(f"[ScreeningAgent] Skipping duplicate record={record.record_id}")
                continue
            result = self.screen(
                record,
                watchlist_version_id=watchlist_version_id,
                watchlist_entries=watchlist_entries,
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_llm_analysis(
        self,
        record: IngestedRecord,
        rule_results: List,
        rule_decision: ScreeningRuleResult,
    ) -> Optional[LLMAnalysis]:
        """Call Claude to analyse the transaction context."""
        try:
            rule_summary = [
                {
                    "rule_id": r.rule_id,
                    "rule": r.rule_name,
                    "result": r.result.value,
                    "detail": r.detail,
                }
                for r in rule_results
            ]

            user_message = json.dumps({
                "transaction_data": record.payload,
                "stream_type": record.stream_type.value,
                "rule_screening_summary": rule_summary,
                "rule_aggregate_decision": rule_decision.value,
                "ingested_at": record.ingested_at.isoformat(),
            }, default=str, indent=2)

            response = self._llm_client.messages.create(
                model="claude-opus-4-5",
                max_tokens=512,
                system=LLM_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_response = response.content[0].text
            parsed = json.loads(raw_response)

            return LLMAnalysis(
                model="claude-opus-4-5",
                prompt_version=LLM_PROMPT_VERSION,
                risk_score=RiskScore(parsed["risk_score"]),
                confidence=float(parsed.get("confidence", 0.8)),
                flags=parsed.get("flags", []),
                narrative=parsed.get("narrative", ""),
                raw_response=raw_response,
            )

        except Exception as exc:
            logger.error(f"[ScreeningAgent] LLM analysis failed: {exc}")
            return None

    def _aggregate_final(
        self,
        rule_decision: ScreeningRuleResult,
        rule_risk: RiskScore,
        llm_analysis: Optional[LLMAnalysis],
        rule_results: List,
    ):
        """
        Combine rule-based and LLM decisions.
        Escalation logic: take the more severe of the two assessments.
        """
        final_risk = rule_risk
        final_decision = rule_decision
        rationale_parts = []

        triggered_rules = [r for r in rule_results if r.result != ScreeningRuleResult.PASS]
        if triggered_rules:
            rationale_parts.append(
                f"Rules triggered: {', '.join(r.rule_name for r in triggered_rules)}."
            )
        else:
            rationale_parts.append("All rule checks passed.")

        if llm_analysis:
            llm_risk_order = [RiskScore.LOW, RiskScore.MEDIUM, RiskScore.HIGH, RiskScore.CRITICAL]
            rule_idx = llm_risk_order.index(rule_risk)
            llm_idx = llm_risk_order.index(llm_analysis.risk_score)

            if llm_idx > rule_idx:
                # LLM sees higher risk — escalate
                final_risk = llm_analysis.risk_score
                if final_risk in (RiskScore.HIGH, RiskScore.CRITICAL):
                    final_decision = ScreeningRuleResult.BLOCK
                elif final_risk == RiskScore.MEDIUM:
                    final_decision = ScreeningRuleResult.FLAG
                rationale_parts.append(
                    f"LLM escalated risk to {final_risk.value} "
                    f"(confidence={llm_analysis.confidence:.0%}): {llm_analysis.narrative}"
                )
            else:
                rationale_parts.append(
                    f"LLM concurred with rule assessment: {llm_analysis.narrative}"
                )

            if llm_analysis.flags:
                rationale_parts.append(f"LLM flags: {', '.join(llm_analysis.flags)}.")

        return final_risk, final_decision, " ".join(rationale_parts)

    def _get_active_watchlist_id(self) -> str:
        """Resolve the most recent active watchlist version for OFAC_SDN."""
        wl = self._ingestion_agent.get_active_watchlist("OFAC_SDN")
        if wl:
            return wl.watchlist_version_id
        # Fallback: create a placeholder version to maintain traceability
        logger.warning(
            "[ScreeningAgent] No OFAC_SDN watchlist found — using placeholder version."
        )
        return "wl-no-list-loaded"

    def _persist(self, result: ScreeningResult) -> None:
        insert_row("screening_results", {
            "screening_id":         result.screening_id,
            "record_id":            result.record_id,
            "watchlist_version_id": result.watchlist_version_id,
            "screened_at":          result.screened_at.isoformat(),
            "rule_results":         json.dumps(
                [r.model_dump() for r in result.rule_results], default=str
            ),
            "llm_analysis":         json.dumps(
                result.llm_analysis.model_dump(), default=str
            ) if result.llm_analysis else None,
            "final_risk_score":     result.final_risk_score.value,
            "final_decision":       result.final_decision.value,
            "decision_rationale":   result.decision_rationale,
        })
