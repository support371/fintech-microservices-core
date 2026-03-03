# LedgerAgent

## Purpose

The Ledger Agent maintains an immutable, append-only record of every significant
event in the Nexus platform — transactions, compliance decisions, security
incidents, and system state changes.

## Responsibilities

- **Transaction Recording** — Persist every fiat-to-BTC conversion, card
  issuance, and fund load with full trace context.
- **Event Aggregation** — Collect events from the Compliance, Security, Platform,
  and Build agents into a unified ledger.
- **Idempotency Enforcement** — Deduplicate events using `trace_id` /
  `transaction_id` to prevent double-recording.
- **Reconciliation** — Provide queries to reconcile ledger entries against
  external provider records (Striga, banking webhooks).

## Inputs

| Field            | Type   | Source                          |
|------------------|--------|---------------------------------|
| `trace_id`       | string | Originating service             |
| `event_type`     | string | Agent or service identifier     |
| `payload`        | object | Event-specific data             |
| `timestamp`      | string | ISO 8601 UTC                    |

## Outputs

| Field          | Type    | Description                            |
|----------------|---------|----------------------------------------|
| `ledger_entry` | object  | The persisted, immutable ledger record |
| `entry_id`     | string  | Unique identifier for the entry        |
| `duplicate`    | boolean | `true` if the event was deduplicated   |

## Integration Points

- Consumes events from **ComplianceAgent**, **SecurityAgent**, and
  **PlatformAgent**
- Backs the reconciliation API used by the admin dashboard
  (`/api/admin/operations`)
- References schema in `foundry/schemas/ledger.schema.json`

## Configuration

See `foundry/schemas/ledger.schema.json` for the full event schema, including
required fields, allowed event types, and retention policies.
