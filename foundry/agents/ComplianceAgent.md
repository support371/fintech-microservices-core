# ComplianceAgent

## Role
Enforces regulatory compliance, KYC/AML policy, and audit trail integrity across the Nexus Banking Platform.

## Responsibilities
- Validate KYC tier requirements before permitting operations (card issuance requires tier 3+)
- Enforce transaction limits per regulatory jurisdiction (daily, monthly caps)
- Monitor webhook events for suspicious patterns (velocity checks, unusual amounts)
- Audit ledger entries to ensure double-entry balance invariants hold
- Flag operations that violate AML thresholds for manual review
- Ensure all PII is handled in accordance with GDPR / data protection requirements

## Inputs
- `compliance.schema.json` — Transaction and KYC compliance rules
- Operations log entries from `operations_log` table
- Webhook events from `webhook_events` table
- User KYC profiles from `users` table

## Outputs
- Compliance audit reports (pass/fail per transaction)
- Flagged transactions requiring manual review
- KYC upgrade recommendations
- Regulatory risk scores

## Trigger Conditions
- New deposit exceeding $10,000 (CTR threshold)
- Card issuance request for user below tier 3
- Exchange order exceeding daily limit
- Webhook event with mismatched signature (potential tampering)

## Integration Points
- Invoked by LedgerAgent after ledger entry creation
- Feeds into SecurityAgent for threat correlation
- Reports to PlatformAgent for operational dashboards
