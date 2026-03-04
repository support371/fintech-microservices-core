# SecurityAgent

## Role
Monitors platform security posture, validates cryptographic operations, detects unauthorized access and anomalous patterns, and enforces replay attack prevention.

## Responsibilities
- Verify HMAC-SHA256 webhook signatures using timing-safe comparison (`crypto.timingSafeEqual`)
- Enforce timestamp validation on webhooks to prevent replay attacks (5-minute drift window)
- Track webhook nonces to detect duplicate/replayed deliveries
- Monitor rate limiter state for distributed brute-force patterns
- Detect anomalous traffic patterns: burst requests, sustained high volume, auth failure floods
- Flag and track IPs that exceed violation or auth failure thresholds
- Validate Bearer token authentication on cron endpoints
- Detect and alert on repeated authentication failures per IP
- Review API route authorization checks for completeness
- Ensure environment secrets are never exposed in logs or responses
- Verify security response headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)

## Inputs
- `security.schema.json` — Webhook verification, rate limiting, anomaly detection, replay protection config
- Webhook signature verification results (HMAC-SHA256 + timestamp + nonce)
- Rate limiter bucket states and anomaly tracker data
- Authentication failure logs
- API response headers
- IP anomaly tracker state (burst count, violation count, auth failures, flagged status)

## Outputs
- Security incident reports with severity (warning/critical)
- Signature verification audit trail
- Rate limit violation alerts with anomaly classification
- Authentication anomaly notifications
- Replay attack detection alerts (stale timestamp, duplicate nonce)
- Flagged IP reports with threat details
- Burst pattern alerts (>10 requests in 5 seconds)
- Brute-force detection alerts (>10 auth failures per IP)

## Anomaly Detection Types
| Type | Trigger | Severity |
|------|---------|----------|
| `burst` | >10 requests in 5s from same IP | warning |
| `sustained` | Repeated rate limit violations | warning → critical |
| `auth_failure` | >10 auth failures from same IP | critical |
| `flagged_ip` | IP exceeded violation or auth thresholds | critical |

## Replay Attack Prevention
- **Timestamp validation**: Reject webhooks with timestamp > 5 minutes old
- **Nonce deduplication**: Track recent nonces in memory, reject duplicates
- **Signed timestamps**: Include timestamp in HMAC payload (Stripe convention: `{timestamp}.{payload}`)
- **Nonce TTL**: Nonces expire after 10 minutes, cleaned periodically

## Trigger Conditions
- Webhook signature verification failure
- Webhook timestamp drift exceeds 5-minute window
- Duplicate webhook nonce detected (replay attempt)
- Rate limit exceeded on any endpoint
- Burst pattern detected (>10 req/5s)
- Authentication failure from any IP
- IP flagged after reaching violation/auth failure threshold
- Cron endpoint accessed without valid Bearer token
- Environment variable access in non-server context
- Missing security response headers

## Integration Points
- Validates all webhook handlers (banking, KYC, cards)
- Feeds threat intelligence and flagged IPs to ComplianceAgent
- Reports critical incidents to PlatformAgent
- Coordinates with BuildAgent for security-aware deployment
- Anomaly data feeds into compliance risk scoring
