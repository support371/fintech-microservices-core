from decimal import Decimal

import pytest

from converter_service.logic import ConversionLogic


def test_sandbox_conversion_is_deterministic_and_non_live(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "sandbox")
    monkeypatch.setenv("ALLOW_LIVE_PAYMENTS", "false")
    monkeypatch.setenv("AML_SINGLE_TRANSACTION_LIMIT", "10000")
    monkeypatch.setenv("SUPPORTED_FIAT_CURRENCIES", "USD")
    monkeypatch.setenv("SANDBOX_BTC_RATES_JSON", '{"USD":"50000"}')

    logic = ConversionLogic()
    result = logic.execute_conversion_and_payout(Decimal("100.00"), "usd", "user-1")

    assert result["status"] == "simulated"
    assert result["payment_mode"] == "sandbox"
    assert result["btc_amount_sent"] == "0.00200000"
    assert result["satoshis_sent"] == 200000


def test_conversion_rejects_amount_above_aml_limit(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "sandbox")
    monkeypatch.setenv("AML_SINGLE_TRANSACTION_LIMIT", "100")
    logic = ConversionLogic()

    with pytest.raises(ValueError, match="AML limit"):
        logic.execute_conversion_and_payout("100.01", "USD", "user-1")


def test_live_mode_fails_closed_without_live_approval(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_PAYMENTS", "false")
    logic = ConversionLogic()

    with pytest.raises(RuntimeError, match="Live payments are disabled"):
        logic.execute_conversion_and_payout("10", "USD", "user-1")
