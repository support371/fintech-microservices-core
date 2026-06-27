"""
Unit tests — AuditTrailAgent chain integrity verification.
Run: pytest tests/unit/test_audit_chain.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from compliance_agents.audit_trail.agent import AuditTrailAgent


class TestAuditChain:
    def setup_method(self):
        self.agent = AuditTrailAgent()

    def test_verify_chain_returns_dict(self):
        result = self.agent.verify_chain_integrity()
        assert isinstance(result, dict)

    def test_chain_has_required_keys(self):
        result = self.agent.verify_chain_integrity()
        assert 'integrity_ok' in result
        assert 'verified_entries' in result
        assert 'quarantined_entries' in result
        assert 'broken_links' in result

    def test_integrity_ok_is_boolean(self):
        result = self.agent.verify_chain_integrity()
        assert isinstance(result['integrity_ok'], bool)

    def test_verified_entries_is_non_negative(self):
        result = self.agent.verify_chain_integrity()
        assert result['verified_entries'] >= 0

    def test_quarantined_entries_is_non_negative(self):
        result = self.agent.verify_chain_integrity()
        assert result['quarantined_entries'] >= 0

    def test_broken_links_is_list(self):
        result = self.agent.verify_chain_integrity()
        assert isinstance(result['broken_links'], list)

    def test_chain_integrity_passes(self):
        """Core assertion — chain must be valid after our repair."""
        result = self.agent.verify_chain_integrity()
        assert result['integrity_ok'] is True, (
            f"Chain broken! broken_links={result['broken_links']}, "
            f"quarantined={result['quarantined_entries']}"
        )
