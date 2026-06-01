# ReportingAgent

## Purpose

The Reporting Agent automates the creation of Suspicious Activity Reports
(SARs) and periodic compliance reports from the immutable audit trail.

All report data is sourced **exclusively** from `AuditTrailAgent.query()` —
no secondary DB queries. This ensures reports are fully consistent with the
audit record and cannot diverge from what was actually decided.

## Responsibilities

- **SAR Generation** — Produce FinCEN-ready Suspicious Activity Reports for
  any user with HIGH or CRITICAL risk flags. Pre-fills all standard fields:
  subject identity, activity period, total amounts, flag categories, narrative,
  supporting audit entry IDs, and all watchlist version IDs used.
- **Automatic SAR Triggering** — The orchestrator auto-generates a SAR whenever
  a screening result scores HIGH or CRITICAL.
- **Compliance Summary Reports** — Periodic reports covering a configurable
  time window: transaction counts by decision, top risk categories, human
  override log with rationale, active watchlist versions, and chain integrity
  verification result.
- **Traceability** — Every SAR includes `supporting_audit_entry_ids` (links
  to specific `AuditEntry` records) and `watchlist_version_ids_used` (full
  provenance of which sanction list was active during screening).

## SAR Fields (pre-filled)

| Field                         | Source                                    |
|-------------------------------|-------------------------------------------|
| `sar_id`                      | Auto-generated (`sar-*`)                  |
| `subject_user_id`             | From screening audit entries              |
| `activity_start / end`        | Query window                              |
| `total_amount / currency`     | Aggregated from audit payload snapshots   |
| `transaction_count`           | Count of screening decision entries       |
| `risk_score`                  | Highest observed across all screenings    |
| `flag_categories`             | Deduplicated LLM flags from all entries   |
| `narrative`                   | Auto-generated plain-English summary      |
| `supporting_audit_entry_ids`  | Exact `AuditEntry.entry_id` references    |
| `watchlist_version_ids_used`  | All `watchlist_version_id` values seen    |
| `status`                      | `draft` → `submitted` → `acknowledged`   |

## Compliance Report Contents

- Transaction decision breakdown (approved / flagged / blocked)
- SAR count for the period
- Human override count and full rationale log
- Top 5 risk flag categories (from LLM analysis)
- Active watchlist versions
- Audit chain integrity verification result

## Implementation

- `compliance_agents/reporting/agent.py`
- `compliance_agents/shared/models.py` → `SARReport`, `ComplianceReport`

## API Endpoints

- `POST /compliance/report/sar` — Generate a SAR for a specific user
- `GET  /compliance/report/compliance?period_hours=24` — Compliance summary
