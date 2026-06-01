# DataIngestionAgent

## Purpose

The Data Ingestion Agent is the entry point for all external data streams
entering the Nexus compliance system. It normalises, deduplicates, and
versions every incoming record before handing it to the Screening Agent.

## Responsibilities

- **Multi-Source Ingestion** — Accept transaction logs, user profiles,
  watchlist updates, webhook events, and card events from any Nexus service.
- **Normalisation** — Strip nulls, uppercase currency codes, coerce amounts
  to float, and ensure a canonical UTC timestamp exists on every record.
- **Content-Addressed Versioning** — Assign a `version_id` (SHA-256 of the
  normalised payload) and a unique `record_id` to every record.
- **Deduplication** — Reject records with matching `version_id`, marking them
  as duplicates and referencing the canonical original.
- **Watchlist Versioning** — Ingest new regulatory watchlist files (OFAC SDN,
  EU Sanctions, etc.) and assign a unique `watchlist_version_id` (SHA-256 of
  the raw file). Every screening decision references this ID.

## Inputs

| Field         | Type   | Source                                          |
|---------------|--------|-------------------------------------------------|
| `stream_type` | string | `transaction_log` / `user_profile` / `watchlist_update` / `webhook_event` / `card_event` |
| `source`      | string | Originating service name                        |
| `payload`     | object | Raw event data from the producing service       |

For watchlist uploads:
| `list_name`      | string | e.g. `OFAC_SDN`, `EU_SANCTIONS`             |
| `raw_content`    | bytes  | Raw watchlist file                           |
| `record_count`   | int    | Number of entries in the list                |
| `effective_date` | string | ISO 8601 date the list is effective          |

## Outputs

| Field          | Type    | Description                                      |
|----------------|---------|--------------------------------------------------|
| `record_id`    | string  | Unique record identifier (`rec-*`)               |
| `version_id`   | string  | SHA-256 content hash of normalised payload       |
| `is_duplicate` | boolean | Whether this record was already seen             |
| `duplicate_of` | string  | `record_id` of the canonical original, if dup   |
| `ingested_at`  | string  | ISO 8601 UTC timestamp of ingestion              |

For watchlists:
| `watchlist_version_id` | string | Unique ID (`wl-*`) for this list version |

## Integration Points

- Feeds `IngestedRecord` objects to the **ScreeningAgent**
- Publishes `data_ingested` / `data_deduplicated` events to the **AuditTrailAgent**
- Called by the **NexusComplianceOrchestrator** at the start of every pipeline run

## Implementation

- `compliance_agents/data_ingestion/agent.py`
- `compliance_agents/shared/models.py` → `IngestedRecord`, `WatchlistVersion`
- `compliance_agents/shared/storage.py` → `ingested_records`, `watchlist_versions` tables

## API Endpoint

`POST /compliance/ingest` — Ingest a single record.
`POST /compliance/watchlist/upload` — Version a new watchlist.
