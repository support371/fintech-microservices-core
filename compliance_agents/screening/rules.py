"""
Rule-based screening engine for the ScreeningAgent.

Rules are evaluated in order. Each rule returns a RuleCheckResult.
Adding new rules requires only implementing a new _rule_* method and
registering it in RULE_REGISTRY.

Current rules (aligned with compliance.schema.json):
  1. Geographic restriction check
  2. Single transaction limit (AML) — default $10,000
  3. Daily aggregate limit (AML) — default $50,000
  4. KYC tier requirement — minimum Tier 3
  5. Structured transaction detection (smurfing)
  6. Rapid velocity check (multiple txns in short window)
  7. Watchlist name match
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from compliance_agents.shared.models import (
    RuleCheckResult,
    ScreeningRuleResult,
)
from compliance_agents.shared.storage import fetch_rows

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (mirrors compliance.schema.json defaults)
# ---------------------------------------------------------------------------

SINGLE_TXN_LIMIT_USD = 10_000.0
DAILY_AGGREGATE_LIMIT_USD = 50_000.0
MIN_KYC_TIER = 3
STRUCTURING_THRESHOLD = 9_500.0    # Transactions just under $10k
VELOCITY_WINDOW_MINUTES = 60
VELOCITY_MAX_COUNT = 5

RESTRICTED_COUNTRIES = {
    "CU", "IR", "KP", "SY", "RU",  # OFAC primary targets
    "BY", "MM", "SD", "ZW",
}


class RuleEngine:
    """
    Stateless rule evaluator. Receives a normalised payload dict
    and returns a list of RuleCheckResult objects.
    """

    def evaluate(
        self,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        watchlist_entries: Optional[List[str]] = None,
    ) -> List[RuleCheckResult]:
        """
        Run all registered rules against the payload.
        Returns results for every rule (pass and fail).
        """
        results: List[RuleCheckResult] = []
        context = {
            "payload": payload,
            "user_id": user_id or payload.get("user_id"),
            "watchlist_entries": watchlist_entries or [],
        }

        for rule_id, rule_name, rule_fn in self._RULE_REGISTRY:
            try:
                result = rule_fn(self, context)
                result.rule_id = rule_id
                result.rule_name = rule_name
                results.append(result)
            except Exception as exc:
                logger.error(f"[RuleEngine] Rule {rule_id} raised an error: {exc}")
                results.append(RuleCheckResult(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    result=ScreeningRuleResult.FLAG,
                    detail=f"Rule evaluation error: {exc}",
                ))

        return results

    def aggregate_decision(self, results: List[RuleCheckResult]) -> ScreeningRuleResult:
        """
        Aggregate rule results into a single decision.
        Any BLOCK → BLOCK. Any FLAG (with no BLOCK) → FLAG. Otherwise PASS.
        """
        if any(r.result == ScreeningRuleResult.BLOCK for r in results):
            return ScreeningRuleResult.BLOCK
        if any(r.result == ScreeningRuleResult.FLAG for r in results):
            return ScreeningRuleResult.FLAG
        return ScreeningRuleResult.PASS

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _rule_geographic_restriction(self, ctx: Dict) -> RuleCheckResult:
        payload = ctx["payload"]
        country = (
            payload.get("country_code")
            or payload.get("country")
            or payload.get("geo_country")
            or ""
        ).upper().strip()

        if country in RESTRICTED_COUNTRIES:
            return RuleCheckResult(
                rule_id="",
                rule_name="",
                result=ScreeningRuleResult.BLOCK,
                detail=f"Transaction originates from OFAC-restricted country: {country}",
                triggered_value=country,
                threshold=list(RESTRICTED_COUNTRIES),
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"Country {country!r} not restricted." if country else "No country field present.",
        )

    def _rule_single_txn_limit(self, ctx: Dict) -> RuleCheckResult:
        payload = ctx["payload"]
        amount = float(payload.get("amount") or payload.get("fiat_amount") or 0)
        currency = payload.get("currency") or payload.get("fiat_currency") or "USD"

        # Simple pass-through: only evaluate USD amounts for now
        if currency != "USD":
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.PASS,
                detail=f"Currency {currency} — limit check skipped (USD only).",
            )

        if amount >= SINGLE_TXN_LIMIT_USD:
            result = ScreeningRuleResult.BLOCK if amount >= SINGLE_TXN_LIMIT_USD * 1.5 else ScreeningRuleResult.FLAG
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=result,
                detail=f"Transaction amount ${amount:,.2f} meets/exceeds single-txn limit ${SINGLE_TXN_LIMIT_USD:,.2f}.",
                triggered_value=amount,
                threshold=SINGLE_TXN_LIMIT_USD,
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"Amount ${amount:,.2f} within single-txn limit.",
        )

    def _rule_daily_aggregate_limit(self, ctx: Dict) -> RuleCheckResult:
        user_id = ctx.get("user_id")
        payload = ctx["payload"]
        amount = float(payload.get("amount") or payload.get("fiat_amount") or 0)

        if not user_id:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.FLAG,
                detail="Cannot check daily aggregate: user_id missing.",
            )

        # Query past 24h transactions for this user from ingested_records
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rows = fetch_rows(
            "ingested_records",
            where="stream_type = 'transaction_log' AND is_duplicate = 0 AND ingested_at >= ? AND payload LIKE ?",
            params=[since, f'%"user_id": "{user_id}"%'],
        )
        daily_total = sum(
            float(json.loads(r["payload"]).get("amount") or json.loads(r["payload"]).get("fiat_amount") or 0)
            for r in rows
        ) + amount

        if daily_total >= DAILY_AGGREGATE_LIMIT_USD:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.BLOCK,
                detail=f"Daily aggregate ${daily_total:,.2f} exceeds limit ${DAILY_AGGREGATE_LIMIT_USD:,.2f}.",
                triggered_value=daily_total,
                threshold=DAILY_AGGREGATE_LIMIT_USD,
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"Daily aggregate ${daily_total:,.2f} within limit.",
        )

    def _rule_kyc_tier(self, ctx: Dict) -> RuleCheckResult:
        payload = ctx["payload"]
        kyc_raw = payload.get("kyc_tier") or payload.get("kyc_status") or ""
        tier: Optional[int] = None
        if isinstance(kyc_raw, int):
            tier = kyc_raw
        elif isinstance(kyc_raw, str) and kyc_raw.startswith("Tier "):
            try:
                tier = int(kyc_raw.split("Tier ")[1])
            except (IndexError, ValueError):
                pass

        if tier is None:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.FLAG,
                detail="KYC tier not present in payload — cannot verify.",
            )
        if tier < MIN_KYC_TIER:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.BLOCK,
                detail=f"KYC Tier {tier} is below minimum required Tier {MIN_KYC_TIER}.",
                triggered_value=tier,
                threshold=MIN_KYC_TIER,
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"KYC Tier {tier} meets minimum requirement.",
        )

    def _rule_structuring_detection(self, ctx: Dict) -> RuleCheckResult:
        """Detect potential smurfing — amounts just below the reporting threshold."""
        payload = ctx["payload"]
        amount = float(payload.get("amount") or payload.get("fiat_amount") or 0)

        if STRUCTURING_THRESHOLD <= amount < SINGLE_TXN_LIMIT_USD:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.FLAG,
                detail=(
                    f"Amount ${amount:,.2f} falls in the structuring risk band "
                    f"(${STRUCTURING_THRESHOLD:,.2f} – ${SINGLE_TXN_LIMIT_USD:,.2f}). "
                    "Possible smurfing activity."
                ),
                triggered_value=amount,
                threshold=STRUCTURING_THRESHOLD,
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail="Amount does not fall in structuring risk band.",
        )

    def _rule_velocity_check(self, ctx: Dict) -> RuleCheckResult:
        """Flag users with unusually high transaction frequency."""
        user_id = ctx.get("user_id")
        if not user_id:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.PASS,
                detail="Velocity check skipped — no user_id.",
            )

        since = (
            datetime.now(timezone.utc) - timedelta(minutes=VELOCITY_WINDOW_MINUTES)
        ).isoformat()

        rows = fetch_rows(
            "ingested_records",
            where=(
                "stream_type = 'transaction_log' AND is_duplicate = 0 "
                "AND ingested_at >= ? AND payload LIKE ?"
            ),
            params=[since, f'%"user_id": "{user_id}"%'],
        )
        count = len(rows)
        if count >= VELOCITY_MAX_COUNT:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.FLAG,
                detail=(
                    f"User {user_id} has {count} transactions in the last "
                    f"{VELOCITY_WINDOW_MINUTES} minutes (limit: {VELOCITY_MAX_COUNT})."
                ),
                triggered_value=count,
                threshold=VELOCITY_MAX_COUNT,
            )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"Velocity OK: {count} transactions in window.",
        )

    def _rule_watchlist_name_match(self, ctx: Dict) -> RuleCheckResult:
        """Check user name / entity name against loaded watchlist entries."""
        payload = ctx["payload"]
        watchlist_entries: List[str] = ctx.get("watchlist_entries", [])

        if not watchlist_entries:
            return RuleCheckResult(
                rule_id="", rule_name="",
                result=ScreeningRuleResult.PASS,
                detail="No watchlist entries loaded for name matching.",
            )

        name_fields = [
            payload.get("full_name"),
            payload.get("first_name"),
            payload.get("last_name"),
            payload.get("entity_name"),
        ]
        names = [n.lower().strip() for n in name_fields if n]

        for entry in watchlist_entries:
            entry_lower = entry.lower().strip()
            for name in names:
                if entry_lower in name or name in entry_lower:
                    return RuleCheckResult(
                        rule_id="", rule_name="",
                        result=ScreeningRuleResult.BLOCK,
                        detail=f"Name match against watchlist entry: '{entry}'.",
                        triggered_value=name,
                        threshold=entry,
                    )
        return RuleCheckResult(
            rule_id="", rule_name="",
            result=ScreeningRuleResult.PASS,
            detail=f"No name matches against {len(watchlist_entries)} watchlist entries.",
        )

    # ------------------------------------------------------------------
    # Rule registry — order matters for readability of results
    # ------------------------------------------------------------------

    _RULE_REGISTRY = [
        ("R001", "Geographic Restriction",     _rule_geographic_restriction),
        ("R002", "Single Transaction Limit",   _rule_single_txn_limit),
        ("R003", "Daily Aggregate Limit",      _rule_daily_aggregate_limit),
        ("R004", "KYC Tier Requirement",       _rule_kyc_tier),
        ("R005", "Structuring Detection",      _rule_structuring_detection),
        ("R006", "Transaction Velocity",       _rule_velocity_check),
        ("R007", "Watchlist Name Match",       _rule_watchlist_name_match),
    ]
