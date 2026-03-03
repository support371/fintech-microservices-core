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

## Outputs

| Field           | Type    | Description                          |
|-----------------|---------|--------------------------------------|
| `build_id`      | string  | Unique build identifier              |
| `status`        | string  | `success` / `failure` / `pending`    |
| `artifacts_url` | string  | Location of published artifacts      |
| `deploy_ready`  | boolean | Whether the build is cleared to ship |

## Integration Points

- Monitors `.github/workflows/python-publish.yml` for CI status
- Triggers the **PlatformAgent** for deployment coordination
- Requires sign-off from **ComplianceAgent** and **SecurityAgent** before deploy
- Records build events via the **LedgerAgent**
- References configuration in `foundry/schemas/build.schema.json`

## Configuration

See `foundry/schemas/build.schema.json` for the full configuration schema,
including build targets, artifact registries, and promotion policies.
