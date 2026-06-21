from common.gateway_auth import validate_gateway_key


def test_gateway_key_requires_configuration(monkeypatch):
    monkeypatch.delenv("NEXUS_GATEWAY_API_KEY", raising=False)
    assert validate_gateway_key("anything") is False


def test_gateway_key_matches_in_constant_time(monkeypatch):
    monkeypatch.setenv("NEXUS_GATEWAY_API_KEY", "test-gateway-key")
    assert validate_gateway_key("test-gateway-key") is True
    assert validate_gateway_key("wrong-key") is False
