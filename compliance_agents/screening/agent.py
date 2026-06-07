"""
Agent 2: ScreeningAgent (with LLM integration)
================================================
Combines rule-based screening with LLM analysis to produce a final risk
score and decision for each IngestedRecord.

LLM provider cascade (tried in order):
  1. OpenAI  — primary  (OPENAI_API_KEY)
  2. Groq    — fallback (GROQ_API_KEY) — free tier, llama-3.3-70b-versatile
  3. None    — rule-only mode (always works)

Pipeline:
  IngestedRecord → Rule Engine (7 rules) → LLM analysis (best available)
                → aggregate decision → ScreeningResult

Environment:
  OPENAI_API_KEY       — OpenAI key (optional, used first)
  OPENAI_MODEL         — model override (default: gpt-4o)
  GROQ_API_KEY         — Groq key (optional, fallback)
  GROQ_MODEL           — model override (default: llama-3.3-70b-versatile)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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

LLM_PROMPT_VERSION = "v2.1.0"   # multi-provider cascade

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

Be concise. The narrative will appear in regulatory audit trails and SAR filings.
Return ONLY the JSON object — no markdown, no explanation."""


def _build_llm_clients() -> List[Tuple[str, Any, str]]:
    """
    Return a list of (provider_label, client, model) tuples in cascade order.
    Only providers with API keys present are included.
    """
    providers = []

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            model  = os.environ.get("OPENAI_MODEL", "gpt-4o")
            providers.append(("openai", client, model))
        except Exception as e:
            logger.warning("[ScreeningAgent] OpenAI init failed: %s", e)

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            model  = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            providers.append(("groq", client, model))
        except Exception as e:
            logger.warning("[ScreeningAgent] Groq init failed: %s", e)

    return providers


class ScreeningAgent:
    """
    Modular screening system: rule engine + multi-provider LLM cascade.

    Usage:
        agent = ScreeningAgent()
        result = agent.screen(record, watchlist_version_id="wl-abc123")
    """

    AGENT_NAME = "ScreeningAgent"

    def __init__(self) -> None:
        init_db()
        self._rule_engine = RuleEngine()
        self._ingestion_agent = DataIngestionAgent()
        self._providers = _build_llm_clients()

        if self._providers:
            labels = [f"{p} ({m})" for p, _, m in self._providers]
            logger.info(
                "[ScreeningAgent] LLM cascade: %s | prompt_version=%s",
                " → ".join(labels), LLM_PROMPT_VERSION,
            )
        else:
            logger.warning(
                "[ScreeningAgent] No LLM keys found — rule-only mode. "
                "Set OPENAI_API_KEY or GROQ_API_KEY to enable LLM analysis."
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
            record:               Normalised record from DataIngestionAgent.
            watchlist_version_id: Watchlist to reference (falls back to latest OFAC_SDN).
            watchlist_entries:    Names from the active watchlist.
            force_llm:            Always run LLM even for clean PASS decisions.

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
        rule_risk     = RULE_DECISION_TO_RISK[rule_decision]

        logger.info(
            "[ScreeningAgent] Rules: record=%s decision=%s risk=%s",
            record.record_id, rule_decision.value, rule_risk.value,
        )

        # ── Step 2: LLM analysis (cascade) ───────────────────────────────
        should_run_llm = (
            force_llm
            or rule_decision != ScreeningRuleResult.PASS
            or record.stream_type.value == "user_profile"
        )

        llm_analysis: Optional[LLMAnalysis] = None
        if should_run_llm and self._providers:
            llm_analysis = self._run_llm_cascade(record, rule_results, rule_decision)

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
            "[ScreeningAgent] Complete: screening_id=%s final=%s risk=%s wl=%s llm=%s",
            result.screening_id, final_decision.value, final_risk.value,
            wl_version_id, llm_analysis.model if llm_analysis else "none",
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
    # Private: multi-provider LLM cascade
    # ------------------------------------------------------------------

    def _run_llm_cascade(
        self,
        record: IngestedRecord,
        rule_results: List,
        rule_decision: ScreeningRuleResult,
    ) -> Optional[LLMAnalysis]:
        """
        Try each LLM provider in order. Returns the first successful result.
        Logs the provider used and why others were skipped.
        """
        user_message = json.dumps({
            "transaction_data":        record.payload,
            "stream_type":             record.stream_type.value,
            "rule_screening_summary": [
                {
                    "rule_id": r.rule_id,
                    "rule":    r.rule_name,
                    "result":  r.result.value,
                    "detail":  r.detail,
                }
                for r in rule_results
            ],
            "rule_aggregate_decision": rule_decision.value,
            "ingested_at":             record.ingested_at.isoformat(),
        }, default=str, indent=2)

        for provider_label, client, model in self._providers:
            result = self._call_provider(provider_label, client, model, user_message)
            if result is not None:
                return result
            logger.warning(
                "[ScreeningAgent] Provider '%s' failed — trying next in cascade.", provider_label
            )

        logger.error("[ScreeningAgent] All LLM providers exhausted — falling back to rule-only.")
        return None

    def _call_provider(
        self,
        provider_label: str,
        client: Any,
        model: str,
        user_message: str,
    ) -> Optional[LLMAnalysis]:
        """Call one LLM provider and parse the response. Returns None on any failure."""
        try:
            # Both OpenAI and Groq share the same chat.completions.create interface
            kwargs: Dict[str, Any] = dict(
                model=model,
                max_tokens=512,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
            )
            # OpenAI supports response_format; Groq does not (uses JSON mode differently)
            if provider_label == "openai":
                kwargs["response_format"] = {"type": "json_object"}

            response     = client.chat.completions.create(**kwargs)
            raw_response = response.choices[0].message.content

            # Strip any accidental markdown fences from models that ignore the instruction
            clean = raw_response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()

            parsed = json.loads(clean)

            logger.info(
                "[ScreeningAgent] LLM success — provider=%s model=%s risk=%s confidence=%.2f",
                provider_label, model,
                parsed.get("risk_score"), parsed.get("confidence", 0.0),
            )

            return LLMAnalysis(
                model=f"{provider_label}/{model}",
                prompt_version=LLM_PROMPT_VERSION,
                risk_score=RiskScore(parsed["risk_score"]),
                confidence=float(parsed.get("confidence", 0.8)),
                flags=parsed.get("flags", []),
                narrative=parsed.get("narrative", ""),
                raw_response=raw_response,   # verbatim — never truncated (GAO-AI-TR.04)
            )

        except Exception as exc:
            logger.error(
                "[ScreeningAgent] Provider '%s' error: %s", provider_label, exc
            )
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
    ) -> Tuple[RiskScore, ScreeningRuleResult, str]:
        """
        Escalation-only logic:
          - LLM can upgrade FLAG → BLOCK if it scores HIGH/CRITICAL
          - LLM cannot downgrade a rule BLOCK (regulatory requirement)
          - Rules always enforce BLOCK
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

        llm_risk_idx  = RISK_ORDER.index(llm_analysis.risk_score)
        rule_risk_idx = RISK_ORDER.index(rule_risk)
        final_risk    = RISK_ORDER[max(llm_risk_idx, rule_risk_idx)]
        final_decision = RISK_TO_DEC[final_risk]

        # Rules always enforce BLOCK — LLM cannot reduce it
        if rule_decision == ScreeningRuleResult.BLOCK:
            final_decision = ScreeningRuleResult.BLOCK
            final_risk     = RISK_ORDER[max(RISK_ORDER.index(RiskScore.HIGH), llm_risk_idx)]

        flags_str = ", ".join(llm_analysis.flags) if llm_analysis.flags else "none"
        rationale = (
            f"Rules: {rule_rationale} | "
            f"LLM ({llm_analysis.model} v{LLM_PROMPT_VERSION}): "
            f"risk={llm_analysis.risk_score.value} confidence={llm_analysis.confidence:.2f} "
            f"flags=[{flags_str}] | "
            f"Narrative: {llm_analysis.narrative}"
        )

        return final_risk, final_decision, rationale

    # ------------------------------------------------------------------
    # Private: watchlist + persistence
    # ------------------------------------------------------------------

    def _get_active_watchlist_id(self) -> str:
        rows = fetch_rows(
            "watchlist_versions",
            where="list_name = ?",
            params=["OFAC_SDN"],
            order_by="loaded_at DESC",
            limit=1,
        )
        if rows:
            return rows[0]["watchlist_version_id"]
        logger.warning("[ScreeningAgent] No OFAC_SDN watchlist — using placeholder.")
        return "wl-placeholder-no-list-loaded"

    def _persist(self, result: ScreeningResult) -> None:
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
