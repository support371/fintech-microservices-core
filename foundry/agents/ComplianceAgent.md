# ComplianceAgent

## Role
Enforces regulatory compliance, KYC/AML policy, and audit trail integrity across the Nexus Banking Platform with jurisdiction-aware rules aligned to FATF recommendations.

## Responsibilities
- Validate KYC tier requirements before permitting operations (jurisdiction-specific minimums)
- Enforce transaction limits per regulatory jurisdiction (daily, monthly caps per FATF risk-based approach)
- Monitor webhook events for suspicious patterns (velocity checks, unusual amounts, structuring)
- Audit ledger entries to ensure double-entry balance invariants hold
- Flag operations that violate AML thresholds for manual review
- Ensure all PII is handled in accordance with GDPR / CCPA / LGPD / regional data protection requirements
- Compute risk scores per transaction using weighted scoring model
- Enforce CTR (Currency Transaction Report) filing requirements per jurisdiction
- Detect structuring attempts (transactions just below CTR thresholds)
- Manage PEP (Politically Exposed Person) enhanced due diligence

## Inputs
- `compliance.schema.json` — Transaction limits, KYC tiers, jurisdiction configs, risk scoring rules
- `privacy.schema.json` — Data protection regime mappings per jurisdiction
- Operations log entries from `operations_log` table
- Webhook events from `webhook_events` table
- User KYC profiles from `users` table
- Jurisdiction configuration from `src/server/compliance.ts`

## Outputs
- Compliance audit reports (pass/fail per transaction with risk score)
- Flagged transactions requiring manual review (score >= 70)
- CTR filing notifications (transactions at or above jurisdiction threshold)
- Structuring alerts (transactions near threshold multiples)
- KYC upgrade recommendations
- Regulatory risk scores (0-100 scale: low/medium/high/critical)
- EDD (Enhanced Due Diligence) requirements for high-risk customers/jurisdictions

## Risk Assessment Factors
| Factor | Max Weight | Description |
|--------|-----------|-------------|
| Amount vs CTR threshold | 30 | Transaction amount relative to jurisdiction CTR |
| KYC tier | 25 | Lower tiers = higher risk |
| PEP status | 20 | Politically exposed persons |
| Transaction velocity | 15 | Transactions per 24h vs jurisdiction limit |
| Account age | 10 | New accounts (< 7 days) are higher risk |
| Jurisdiction EDD | 10 | Some jurisdictions require EDD by default |

## Jurisdiction Coverage
| Code | Region | CTR Threshold | Data Protection |
|------|--------|--------------|-----------------|
| US | United States | $10,000 USD | CCPA |
| EU | European Union | €10,000 EUR | GDPR |
| UK | United Kingdom | £10,000 GBP | GDPR |
| JP | Japan | ¥2,000,000 JPY | PIPA |
| AE | UAE | 55,000 AED | — |
| BR | Brazil | R$50,000 BRL | LGPD |

## Trigger Conditions
- New deposit exceeding jurisdiction CTR threshold
- Transaction amount >= structuring detection multiple of CTR
- Card issuance request for user below jurisdiction minimum tier
- Exchange order exceeding jurisdiction exchange limit
- Risk score >= 50 (requires EDD)
- Risk score >= 70 (requires manual review)
- PEP-flagged customer initiating any financial operation
- Webhook event with mismatched signature (potential tampering)

## Integration Points
- Invoked by LedgerAgent after ledger entry creation
- Feeds into SecurityAgent for threat correlation
- Reports to PlatformAgent for operational dashboards
- Coordinates with PrivacyAgent (via privacy.schema.json) for data protection compliance
- References jurisdiction configs from compliance.ts risk engine
