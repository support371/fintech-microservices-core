from common.security import sign_internal_request, verify_internal_request


def test_internal_signature_round_trip():
    payload = b'{"amount":"25.00"}'
    timestamp, signature = sign_internal_request("test-secret", payload, timestamp=1_000)

    assert verify_internal_request(
        "test-secret",
        payload,
        timestamp,
        signature,
        now=1_000,
    )


def test_internal_signature_rejects_tampering_and_stale_requests():
    payload = b'{"amount":"25.00"}'
    timestamp, signature = sign_internal_request("test-secret", payload, timestamp=1_000)

    assert not verify_internal_request(
        "test-secret",
        b'{"amount":"26.00"}',
        timestamp,
        signature,
        now=1_000,
    )
    assert not verify_internal_request(
        "test-secret",
        payload,
        timestamp,
        signature,
        now=1_301,
        tolerance_seconds=300,
    )
