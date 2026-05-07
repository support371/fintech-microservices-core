# BuildAgent

## Purpose

The Build Agent automates the continuous integration and deployment pipeline for
the Nexus platform. It validates code changes, runs tests, builds artifacts, and
coordinates deployment through the locked-build workflow.

## Responsibilities

- **CI Pipeline Execution** — Trigger and monitor GitHub Actions workflows
  (`.github/workflows/python-publish.yml`) on code changes.
- **Artifact Management** — Build Python distribution packages and Docker images
  for `card_platform_service` and `converter_service`.
- **Pre-deploy Validation** — Run the full agent validation chain (Compliance →
  Security → Ledger) before allowing deployment to proceed.
- **Locked-Build Enforcement** — Ensure that only builds passing all agent checks
  are promoted to production, as defined in
  `foundry/workflows/nexus-locked-build.yaml`.

## Inputs

| Field          | Type   | Source                            |
|----------------|--------|-----------------------------------|
| `commit_sha`   | string | Git / GitHub Actions              |
| `branch`       | string | Git ref                           |
| `trigger`      | string | `push` / `release` / `manual`    |
| `artifacts`    | array  | Built distribution files          |
| `input_pack`   | object | Gate results from all four agents |

### Input Pack

The BuildAgent receives an `input_pack` containing the outputs of each
agent validation gate. Every key maps to the gate's JSON output:

| Key          | Source Gate       | Expected `status`            |
|--------------|-------------------|------------------------------|
| `COMPLIANCE` | compliance-gate   | `APPROVED` or `REJECTED`     |
| `SECURITY`   | security-gate     | `APPROVED` or `REJECTED`     |
| `LEDGER`     | ledger-gate       | `APPROVED` or `REJECTED`     |
| `PLATFORM`   | platform-gate     | `APPROVED` or `REJECTED`     |

If any gate returned `REJECTED`, the BuildAgent MUST emit `"verdict": "BLOCKED"`.

## Outputs

The BuildAgent emits machine-readable JSON:

| Field           | Type    | Description                                        |
|-----------------|---------|----------------------------------------------------|
| `verdict`       | string  | `READY` (all gates APPROVED) or `BLOCKED`          |
| `build_id`      | string  | Unique build identifier                            |
| `reason`        | string  | Human-readable explanation of the verdict          |
| `gate_results`  | object  | Per-gate status: `{ COMPLIANCE, SECURITY, LEDGER, PLATFORM }` |

## Integration Points

- Monitors `.github/workflows/python-publish.yml` for CI status
- Receives the full input pack from **ComplianceAgent**, **SecurityAgent**,
  **LedgerAgent**, and **PlatformAgent** before making a READY/BLOCKED decision
- Triggers the **PlatformAgent** for deployment coordination when verdict is READY
- Records build events via the **LedgerAgent**
- References configuration in `foundry/schemas/build.schema.json`

## Configuration

See `foundry/schemas/build.schema.json` for the full configuration schema,
including build targets, artifact registries, and promotion policies.
