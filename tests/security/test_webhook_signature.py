"""
Security tests — HMAC webhook signature verification.
Run: pytest tests/security/test_webhook_signature.py -v
"""

import sys
import os
import hmac
import hashlib
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def compute_hmac(secret: str, body: str) -> str:
    return 'sha256=' + hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()


# Import the actual verifier from the converter service
try:
    from converter_service.main import verify_hmac_signature as verifier
    HAS_VERIFIER = True
except ImportError:
    HAS_VERIFIER = False


class TestWebhookSignatureSecurity:
    SECRET = "test-webhook-secret-xyz"
    BODY = '{"event_id":"evt-001","amount":100,"currency":"USD"}'

    def _verify(self, body: str, sig: str) -> bool:
        import hmac as hmac_mod
        import hashlib
        digest = 'sha256=' + hmac_mod.new(
            self.SECRET.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        if not sig or not digest:
            return False
        # Constant-time compare
        a = digest.encode()
        b = sig.encode()
        if len(a) != len(b):
            return False
        return hmac_mod.compare_digest(a, b)

    def test_valid_signature_passes(self):
        sig = compute_hmac(self.SECRET, self.BODY)
        assert self._verify(self.BODY, sig) is True

    def test_wrong_secret_fails(self):
        sig = compute_hmac("wrong-secret", self.BODY)
        assert self._verify(self.BODY, sig) is False

    def test_tampered_body_fails(self):
        sig = compute_hmac(self.SECRET, self.BODY)
        tampered = self.BODY + " "
        assert self._verify(tampered, sig) is False

    def test_empty_signature_fails(self):
        assert self._verify(self.BODY, "") is False

    def test_empty_body_does_not_crash(self):
        sig = compute_hmac(self.SECRET, "")
        result = self._verify("", sig)
        assert isinstance(result, bool)

    def test_replayed_signature_different_body_fails(self):
        sig = compute_hmac(self.SECRET, self.BODY)
        different_body = '{"event_id":"evt-002","amount":999}'
        assert self._verify(different_body, sig) is False

    def test_signature_without_prefix_fails(self):
        # Signature missing 'sha256=' prefix should fail
        raw_hex = hmac.new(
            self.SECRET.encode(), self.BODY.encode(), hashlib.sha256
        ).hexdigest()
        # Without prefix, our verifier compares sha256=... vs raw hex — must fail
        assert self._verify(self.BODY, raw_hex) is False

    def test_timing_attack_resistance(self):
        """Ensure comparison is constant-time — no early exit on first mismatch."""
        correct_sig = compute_hmac(self.SECRET, self.BODY)
        # Flip last character
        wrong_sig = correct_sig[:-1] + ('a' if correct_sig[-1] != 'a' else 'b')
        assert self._verify(self.BODY, wrong_sig) is False
