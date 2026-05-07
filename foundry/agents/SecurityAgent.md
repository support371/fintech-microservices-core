# SecurityAgent

## Purpose

The Security Agent safeguards the Nexus platform by validating cryptographic
signatures, enforcing authentication policies, and monitoring for anomalous
activity across all service boundaries.

## Responsibilities

- **Webhook Signature Validation** — Verify HMAC-SHA256 signatures on inbound
  webhooks from external providers (e.g., Striga `X-Signature` header).
- **Request Authentication** — Ensure internal service-to-service calls carry
  valid credentials (Bearer tokens, API keys).
- **Rate Limiting** — Enforce configurable rate limits on public-facing endpoints
  to mitigate abuse.
- **Anomaly Detection** — Flag unusual patterns such as repeated failed
  signature checks or unexpected source IPs.

## Inputs

| Field              | Type   | Source                         |
|--------------------|--------|--------------------------------|
| `payload_raw`      | bytes  | Raw HTTP request body          |
| `signature_header` | string | `X-Signature` HTTP header      |
| `source_ip`        | string | Request metadata               |
| `endpoint`         | string | Target route path              |
| `auth_header`      | string | `Authorization` HTTP header    |

## Outputs

| Field            | Type    | Description                          |
|------------------|---------|--------------------------------------|
| `valid`          | boolean | Whether the request passed checks    |
| `threat_level`   | string  | `none` / `low` / `medium` / `high`  |
| `security_event` | object  | Structured event for audit logging   |

## Integration Points

- Wraps `converter_service` → `validate_webhook_signature()` for HMAC checks
- Feeds security events to the **LedgerAgent** for immutable logging
- References policies defined in `foundry/schemas/security.schema.json`

## Configuration

See `foundry/schemas/security.schema.json` for the full configuration schema,
including HMAC algorithms, rate-limit windows, and threat-level thresholds.
