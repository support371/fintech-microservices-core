"""
Agent 2: ScreeningAgent (with LLM integration)
================================================
Combines rule-based screening with OpenAI LLM analysis to produce
a final risk score and decision for each IngestedRecord.

Pipeline:
  IngestedRecord → Rule Engine (7 rules) → LLM analysis (OpenAI)
                → aggregate decision → ScreeningResult
                → emit AuditEntry via AuditTrailAgent

CRITICAL: Every ScreeningResult records the watchlist_version_id that
was active at screening time. This is a hard regulatory requirement.

LLM Role (OpenAI):
  - Analyses the full normalised payload + all rule results
  - Identifies qualitative / contextual red flags that rules miss
  - Assigns an independent risk score (low/medium/high/critical)
  - Provides a plain-English narrative for the audit record
  - Its raw response is stored verbatim in the audit trail

Environment:
  OPENAI_API_KEY   — required for LLM analysis; set via set_secrets
  OPENAI_MODEL     — optional model override (default: gpt-4o)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openai import OpenAI

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

LLM_PROMPT_VERSION = "v2.0.0"   # bumped — now OpenAI-backed

LLM_SYSTEM_PROMPT = """You are a senior AML (Anti-Money Laundering) compliance analyst \
for the Nexus fintech platform. Your job is to review financial transaction data and \
rule-based screening results, then provide an expert qualitative risk assessment.

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

Common flags: structuring, velocity_spike, geographic_risk, watchlist_proximity,
kyc_mismatch, round_amount_pattern, unusual_hours, beneficiary_risk, layering_pattern, smurfing

Be concise. The narrative will appear in regulatory audit trails and SAR filings."""


class ScreeningAgent:
    """
    Modular screening system combining rule-based logic with OpenAI LLM analysis.

    Usage:
        agent = ScreeningAgent()
        result = agent.screen(record, watchlist_version_id="wl-abc123")
    """

    AGENT_NAME = "ScreeningAgent"

    # Model used for LLM analysis — override with OPENAI_MODEL env var
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self) -> None:
        init_db()
        self._rule_engine = RuleEngine()
        self._ingestion_agent = DataIngestionAgent()

        api_key = os.environ.get("OPENAI_API_KEY")
        self._model = os.environ.get("OPENAI_MODEL", self.DEFAULT_MODEL)
        self._llm_client: Optional[OpenAI] = OpenAI(api_key=api_key) if api_key else None

        if not self._llm_client:
            logger.warning(
                "[ScreeningAgent] OPENAI_API_KEY not set — LLM analysis disabled. "
                "Rule-based screening will still run."
            )
        else:
            logger.info(
                "[ScreeningAgent] OpenAI LLM enabled — model=%s prompt_version=%s",
                self._model, LLM_PROMPT_VERSION,
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
            "[ScreeningAgent] Rules: record=%s decision=%s risk=%s",
            record.record_id, rule_decision.value, rule_risk.value,
        )

        # ── Step 2: LLM analysis (OpenAI) ────────────────────────────────
        # Run LLM when: forced, rule decision is not a clean PASS,
        # or the stream type is user_profile (behavioural analysis always on)
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
            "[ScreeningAgent] Complete: screening_id=%s final=%s risk=%s wl=%s",
            result.screening_id, final_decision.value, final_risk.value, wl_version_id,
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
                logger.debug("[ScreeningAgent] Skipping duplicate record=%s", record.record_id)
                continue
            result = self.screen(
                record,
                watchlist_version_id=watchlist_version_id,
                watchlist_entries=watchlist_entries,
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private: LLM analysis via OpenAI
    # ------------------------------------------------------------------

    def _run_llm_analysis(
        self,
        record: IngestedRecord,
        rule_results: List,
        rule_decision: ScreeningRuleResult,
    ) -> Optional[LLMAnalysis]:
        """
        Send the transaction + rule context to OpenAI and parse the response.
        Raw response is stored verbatim — never truncated (GAO-AI-TR.04).
        """
        try:
            rule_summary = [
                {
                    "rule_id": r.rule_id,
                    "rule":    r.rule_name,
                    "result":  r.result.value,
                    "detail":  r.detail,
                }
                for r in rule_results
            ]

            user_message = json.dumps({
                "transaction_data":         record.payload,
                "stream_type":              record.stream_type.value,
                "rule_screening_summary":   rule_summary,
                "rule_aggregate_decision":  rule_decision.value,
                "ingested_at":              record.ingested_at.isoformat(),
            }, default=str, indent=2)

            response = self._llm_client.chat.completions.create(
                model=self._model,
                max_tokens=512,
                temperature=0.1,   # low temp for consistent, deterministic compliance output
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
            )

            raw_response = response.choices[0].message.content
            parsed = json.loads(raw_response)

            return LLMAnalysis(
                model=self._model,
                prompt_version=LLM_PROMPT_VERSION,
                risk_score=RiskScore(parsed["risk_score"]),
                confidence=float(parsed.get("confidence", 0.8)),
                flags=parsed.get("flags", []),
                narrative=parsed.get("narrative", ""),
                raw_response=raw_response,   # verbatim — never truncated
            )

        except Exception as exc:
            logger.error("[ScreeningAgent] LLM analysis failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Private: decision aggregation
    # ------------------------------------------------------------------

    def _aggregate_final(
        self,
        rule_decision: ScreeningRuleResult,
        rule_risk: RiskScore,
        llm_analysis: Optional[LLMAnalysis],
        rule_results: List,
    ):
        """
        Combine rule-based and LLM decisions.

        Escalation-only logic:
          - LLM can upgrade a FLAG → BLOCK if it scores HIGH/CRITICAL
          - LLM cannot downgrade a BLOCK to PASS or FLAG
          - Rules always win on BLOCK (regulatory requirement)
        """
        RISK_ORDER  = [RiskScore.LOW, RiskScore.MEDIUM, RiskScore.HIGH, RiskScore.CRITICAL]
        RISK_TO_DEC = {
            RiskScore.LOW:      ScreeningRuleResult.PASS,
            RiskScore.MEDIUM:   ScreeningRuleResult.FLAG,
            RiskScore.HIGH:     ScreeningRuleResult.BLOCK,
            RiskScore.CRITICAL: ScreeningRuleResult.BLOCK,
        }

        triggered = [r for r in rule_results if r.result != ScreeningRuleResult.PASS]
        rule_rationale = (
            "; ".join(f"[{r.rule_id}] {r.detail}" for r in triggered)
            if triggered else "All rule checks passed."
        )

        if not llm_analysis:
            return rule_risk, rule_decision, f"Rule-based: {rule_rationale}"

        # Take the more severe of rule vs LLM risk
        llm_risk_idx  = RISK_ORDER.index(llm_analysis.risk_score)
        rule_risk_idx = RISK_ORDER.index(rule_risk)
        final_risk    = RISK_ORDER[max(llm_risk_idx, rule_risk_idx)]
        final_decision = RISK_TO_DEC[final_risk]

        # Rules always enforce BLOCK — LLM cannot reduce a rule BLOCK
        if rule_decision == ScreeningRuleResult.BLOCK:
            final_decision = ScreeningRuleResult.BLOCK
            final_risk     = RISK_ORDER[max(RISK_ORDER.index(RiskScore.HIGH), llm_risk_idx)]

        flags_str = ", ".join(llm_analysis.flags) if llm_analysis.flags else "none"
        rationale = (
            f"Rules: {rule_rationale} | "
            f"LLM ({self._model} v{LLM_PROMPT_VERSION}): "
            f"risk={llm_analysis.risk_score.value} confidence={llm_analysis.confidence:.2f} "
            f"flags=[{flags_str}] | "
            f"Narrative: {llm_analysis.narrative}"
        )

        return final_risk, final_decision, rationale

    # ------------------------------------------------------------------
    # Private: watchlist + persistence helpers
    # ------------------------------------------------------------------

    def _get_active_watchlist_id(self) -> str:
        """Return the most recently loaded OFAC_SDN watchlist version ID."""
        rows = fetch_rows(
            "watchlist_versions",
            where="list_name = ?",
            params=["OFAC_SDN"],
            order_by="loaded_at DESC",
            limit=1,
        )
        if rows:
            return rows[0]["watchlist_version_id"]
        logger.warning("[ScreeningAgent] No OFAC_SDN watchlist found — using placeholder version.")
        return "wl-placeholder-no-list-loaded"

    def _persist(self, result: ScreeningResult) -> None:
        """Persist screening result to the screening_results table."""
        insert_row(
            "screening_results",
            {
                "screening_id":         result.screening_id,
                "record_id":            result.record_id,
                "watchlist_version_id": result.watchlist_version_id,
                "screened_at":          result.screened_at.isoformat(),
                "final_risk_score":     result.final_risk_score.value,
                "final_decision":       result.final_decision.value,
                "decision_rationale":   result.decision_rationale,
                "llm_model":            result.llm_analysis.model if result.llm_analysis else None,
                "llm_prompt_version":   result.llm_analysis.prompt_version if result.llm_analysis else None,
                "has_llm_analysis":     1 if result.llm_analysis else 0,
            },
        )
