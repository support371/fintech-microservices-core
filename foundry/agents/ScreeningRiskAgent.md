# ScreeningRiskAgent

## Purpose

The Screening & Risk Agent combines rule-based logic with Claude LLM analysis
to produce a definitive risk score and compliance decision for every ingested
record. It is the intelligence layer of the Nexus compliance system.

## Responsibilities

- **Rule-Based Screening** — Apply 7 configurable compliance rules for initial
  categorisation (geographic restriction, AML limits, KYC tier, structuring
  detection, velocity, watchlist name matching).
- **LLM Analysis (Claude)** — For flagged or blocked records, send the full
  transaction context + rule results to Claude for qualitative risk analysis.
  Claude identifies patterns that rules miss (layering, structuring intent,
  behavioural anomalies) and assigns an independent risk score.
- **Risk Score Assignment** — Aggregate rule + LLM results into a final
  `low / medium / high / critical` risk score.
- **Watchlist Version Tracking** — Every screening result records the exact
  `watchlist_version_id` that was active — a hard regulatory requirement.
- **Escalation Logic** — The LLM can escalate a decision beyond what rules
  determined; it cannot de-escalate a BLOCK to PASS.

## Rules

| Rule ID | Name                      | Action on Trigger |
|---------|---------------------------|-------------------|
| R001    | Geographic Restriction    | BLOCK             |
| R002    | Single Transaction Limit  | FLAG / BLOCK      |
| R003    | Daily Aggregate Limit     | BLOCK             |
| R004    | KYC Tier Requirement      | BLOCK             |
| R005    | Structuring Detection     | FLAG              |
| R006    | Transaction Velocity      | FLAG              |
| R007    | Watchlist Name Match      | BLOCK             |

## LLM Integration

- **Model**: Claude (claude-opus-4-5)
- **Prompt version**: tracked in `LLMAnalysis.prompt_version`
- **Input**: normalised payload + all rule results
- **Output**: `{ risk_score, confidence, flags, narrative }`
- **Raw response**: stored verbatim in the audit trail — never truncated

## Inputs

| Field                  | Type            | Source                     |
|------------------------|-----------------|----------------------------|
| `record`               | IngestedRecord  | DataIngestionAgent output  |
| `watchlist_version_id` | string          | Active watchlist version   |
| `watchlist_entries`    | list\[string\]  | Names from active watchlist|
| `force_llm`            | boolean         | Always run LLM if true     |

## Outputs

| Field                  | Type              | Description                          |
|------------------------|-------------------|--------------------------------------|
| `screening_id`         | string            | Unique screening result ID (`scr-*`) |
| `watchlist_version_id` | string            | Watchlist version used (CRITICAL)    |
| `rule_results`         | list              | Per-rule pass/flag/block results     |
| `llm_analysis`         | LLMAnalysis       | Full Claude output (if run)          |
| `final_risk_score`     | low/medium/high   | Aggregated final risk                |
| `final_decision`       | pass/flag/block   | Enforcement action                   |
| `decision_rationale`   | string            | Human-readable combined explanation  |

## Implementation

- `compliance_agents/screening/agent.py`
- `compliance_agents/screening/rules.py`
- `compliance_agents/shared/models.py` → `ScreeningResult`, `LLMAnalysis`, `RuleCheckResult`

## API Endpoint

`POST /compliance/screen` — Full ingest + screen pipeline.
