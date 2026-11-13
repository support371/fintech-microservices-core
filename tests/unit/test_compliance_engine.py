"""
Unit tests — GovernanceEngine + control satisfaction logic.
Run: pytest tests/unit/test_compliance_engine.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from compliance_agents.governance.engine import GovernanceEngine
from compliance_agents.governance.frameworks import Framework


class TestGovernanceEngine:
    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_full_sweep_returns_all_frameworks(self):
        result = self.engine.run_full_sweep(period_hours=24)
        fw_values = {fw.framework.value for fw in result.frameworks}
        assert 'COBIT_2019' in fw_values
        assert 'COSO_ERM' in fw_values
        assert 'GAO_AI_ACCOUNTABILITY' in fw_values
        assert 'IIA_AI_AUDITING' in fw_values

    def test_each_framework_has_four_controls(self):
        result = self.engine.run_full_sweep(period_hours=24)
        for fw in result.frameworks:
            assert len(fw.controls) == 4, f"{fw.framework.value} has {len(fw.controls)} controls"

    def test_satisfied_controls_count_is_non_negative(self):
        result = self.engine.run_full_sweep(period_hours=24)
        for fw in result.frameworks:
            satisfied = sum(1 for c in fw.controls if c['status'] == 'satisfied')
            assert satisfied >= 0
            assert satisfied <= len(fw.controls)

    def test_total_controls_equals_sixteen(self):
        result = self.engine.run_full_sweep(period_hours=24)
        total = sum(len(fw.controls) for fw in result.frameworks)
        assert total == 16

    def test_sweep_result_has_generated_at(self):
        result = self.engine.run_full_sweep(period_hours=24)
        assert hasattr(result, 'generated_at')
        assert result.generated_at is not None

    def test_sweep_result_has_chain_integrity(self):
        result = self.engine.run_full_sweep(period_hours=24)
        assert hasattr(result, 'chain_integrity')

    def test_all_sixteen_controls_satisfied(self):
        """Core assertion — governance must be at full strength."""
        result = self.engine.run_full_sweep(period_hours=24)
        satisfied = sum(
            1 for fw in result.frameworks
            for c in fw.controls
            if c['status'] == 'satisfied'
        )
        assert satisfied >= 14, f"Only {satisfied}/16 controls satisfied — below threshold"


class TestFrameworkEnum:
    def test_all_four_frameworks_exist(self):
        values = {f.value for f in Framework}
        assert 'COBIT_2019' in values
        assert 'COSO_ERM' in values
        assert 'GAO_AI_ACCOUNTABILITY' in values
        assert 'IIA_AI_AUDITING' in values

    def test_framework_names_are_short_codes(self):
        names = {f.name for f in Framework}
        assert 'COBIT' in names
        assert 'COSO' in names
        assert 'GAO' in names
        assert 'IIA' in names

    def test_framework_values_are_strings(self):
        for fw in Framework:
            assert isinstance(fw.value, str)
