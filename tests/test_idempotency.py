from converter_service.idempotency import IdempotencyStore


def test_in_memory_idempotency_for_non_production(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    store = IdempotencyStore()

    assert store.begin("tx-1") is True
    assert store.begin("tx-1") is False
    assert store.get_completed_response("tx-1") is None

    response = {"status": "simulated"}
    store.complete("tx-1", response)
    assert store.get_completed_response("tx-1") == response


def test_production_requires_persistent_idempotency(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    store = IdempotencyStore()

    try:
        store.begin("tx-1")
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("production idempotency must fail closed without a database")
