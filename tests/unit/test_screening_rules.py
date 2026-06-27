"""
Unit tests — ScreeningAgent RuleEngine (no LLM required).
RuleEngine.evaluate takes a plain dict payload + optional user_id.
Run: pytest tests/unit/test_screening_rules.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from compliance_agents.screening.rules import RuleEngine, ScreeningRuleResult


def make_payload(**kwargs) -> dict:
    defaults = {
        'user_id': 'user-test-001',
        'amount': 100.0,
        'currency': 'USD',
        'transaction_type': 'deposit',
        'counterparty': 'bank-XYZ',
    }
    defaults.update(kwargs)
    return defaults


class TestRuleEngine:
    def setup_method(self):
        self.engine = RuleEngine()

    def test_evaluate_returns_list(self):
        results = self.engine.evaluate(make_payload())
        assert isinstance(results, list)

    def test_each_result_has_rule_id(self):
        results = self.engine.evaluate(make_payload())
        for r in results:
            assert hasattr(r, 'rule_id'), f"Result missing rule_id: {r}"
            assert r.rule_id, "rule_id must not be empty"

    def test_each_result_has_rule_name(self):
        results = self.engine.evaluate(make_payload())
        for r in results:
            assert hasattr(r, 'rule_name'), f"Result missing rule_name: {r}"

    def test_each_result_has_result_field(self):
        results = self.engine.evaluate(make_payload())
        for r in results:
            assert hasattr(r, 'result')
            assert isinstance(r.result, ScreeningRuleResult)

    def test_low_amount_does_not_block(self):
        """$500 is well below AML threshold — should not produce a BLOCK."""
        results = self.engine.evaluate(make_payload(amount=500.0))
        blocks = [r for r in results if r.result == ScreeningRuleResult.BLOCK]
        assert len(blocks) == 0, f"Unexpected blocks on $500 tx: {[b.rule_id for b in blocks]}"

    def test_high_amount_triggers_flag_or_block(self):
        """$15,000 exceeds typical AML threshold — should produce at least one FLAG or BLOCK."""
        results = self.engine.evaluate(make_payload(amount=15_000.0))
        non_pass = [r for r in results if r.result != ScreeningRuleResult.PASS]
        assert len(non_pass) >= 1, "Expected at least one flag/block on $15k transaction"

    def test_zero_amount_does_not_crash(self):
        results = self.engine.evaluate(make_payload(amount=0.0))
        assert isinstance(results, list)

    def test_negative_amount_does_not_crash(self):
        results = self.engine.evaluate(make_payload(amount=-100.0))
        assert isinstance(results, list)

    def test_missing_user_id_does_not_crash(self):
        payload = make_payload()
        del payload['user_id']
        results = self.engine.evaluate(payload, user_id=None)
        assert isinstance(results, list)

    def test_at_least_one_rule_registered(self):
        """Sanity check — the engine must have rules loaded."""
        results = self.engine.evaluate(make_payload())
        assert len(results) >= 1, "RuleEngine has no registered rules"
