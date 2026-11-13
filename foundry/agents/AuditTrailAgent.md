# AuditTrailAgent (Enhanced)

## Purpose

The Audit Trail Agent creates and maintains an append-only, tamper-proof log
of every decision, flag, action, and human override in the Nexus compliance
system. It is the source of truth for all regulatory and legal enquiries.

## Immutability Guarantees

The audit log is protected by three independent layers:

1. **Database triggers** — SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers
   on the `audit_log` table raise `ABORT` errors, making mutation impossible
   at the storage engine level.

2. **Application-level enforcement** — The `AuditTrailAgent` class exposes
   zero update or delete methods. The only write path is `_append()`.

3. **Hash-chain** — Each entry stores `prev_entry_hash` (SHA-256 of the prior
   entry's canonical JSON). Any deletion, insertion, or modification of any
   entry breaks the chain, which is detected by `verify_chain_integrity()`.

## Human Override Policy

Every human override **MUST** include a `rationale` of at least 10 characters.
The rationale is stored verbatim in the audit entry `payload.override_rationale`
and is linked to the override via the `human_override` structured field.

This directly prevents audit exposure: the "why" is permanently on record,
written at the moment of the decision, and cannot be changed retroactively.

## Queryability

The audit trail is queryable by:
- `event_type` (e.g. `transaction_blocked`, `human_override`)
- `record_id` — all events for a specific transaction
- `screening_id` — all events for a specific screening run
- `watchlist_version_id` — all screenings using a specific list
- Date range (`from_dt` / `to_dt`)
- `human_overrides_only` — filter to override entries only

## Event Types

| Event Type                    | Producer Agent     |
|-------------------------------|--------------------|
| `data_ingested`               | DataIngestionAgent |
| `data_deduplicated`           | DataIngestionAgent |
| `watchlist_versioned`         | DataIngestionAgent |
| `rule_screening_complete`     | ScreeningAgent     |
| `llm_analysis_complete`       | ScreeningAgent     |
| `risk_score_assigned`         | ScreeningAgent     |
| `transaction_approved`        | ScreeningAgent     |
| `transaction_flagged`         | ScreeningAgent     |
| `transaction_blocked`         | ScreeningAgent     |
| `human_override`              | HumanAnalyst       |
| `sar_generated`               | ReportingAgent     |
| `compliance_report_generated` | ReportingAgent     |
| `system_event`                | Any agent          |

## Implementation

- `compliance_agents/audit_trail/agent.py`
- `compliance_agents/shared/models.py` → `AuditEntry`, `HumanOverride`
- `compliance_agents/shared/storage.py` → `audit_log` table + triggers

## API Endpoints

- `POST /compliance/override` — Record a human override
- `POST /compliance/audit/query` — Query audit entries
- `GET  /compliance/audit/integrity` — Verify hash-chain integrity
