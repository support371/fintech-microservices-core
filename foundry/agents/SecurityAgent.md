# SecurityAgent

## Role
Monitors platform security posture, validates cryptographic operations, and detects unauthorized access attempts.

## Responsibilities
- Verify HMAC-SHA256 webhook signatures using timing-safe comparison
- Monitor rate limiter state for distributed brute-force patterns
- Validate Bearer token authentication on cron endpoints
- Detect and alert on repeated authentication failures
- Review API route authorization checks for completeness
- Ensure environment secrets are never exposed in logs or responses

## Inputs
- `security.schema.json` — Security policy configuration
- Webhook signature verification results
- Rate limiter bucket states
- Authentication failure logs
- API response headers

## Outputs
- Security incident reports
- Signature verification audit trail
- Rate limit violation alerts
- Authentication anomaly notifications

## Trigger Conditions
- Webhook signature verification failure
- Rate limit exceeded on any endpoint
- Authentication failure from new IP
- Cron endpoint accessed without valid Bearer token
- Environment variable access in non-server context

## Integration Points
- Validates all webhook handlers (banking, KYC, cards)
- Feeds threat intelligence to ComplianceAgent
- Reports critical incidents to PlatformAgent
- Coordinates with BuildAgent for security-aware deployment
