# PlatformAgent

## Purpose

The Platform Agent orchestrates high-level operations across the Nexus platform
services. It coordinates card issuance, fund loading, and webhook processing by
delegating to the appropriate microservices and agents.

## Responsibilities

- **Workflow Orchestration** — Execute multi-step workflows such as the
  nexus-locked-build pipeline defined in
  `foundry/workflows/nexus-locked-build.yaml`.
- **Service Health Monitoring** — Poll health endpoints of `card_platform_service`
  and `converter_service` to maintain an up-to-date status map.
- **Error Recovery** — Retry failed operations with configurable back-off and
  escalate to the Security Agent when retries are exhausted.
- **Deployment Coordination** — Ensure that new deployments pass all agent
  validations before traffic is switched.

## Inputs

| Field           | Type   | Source                       |
|-----------------|--------|------------------------------|
| `workflow_id`   | string | Workflow definition          |
| `trigger`       | string | `manual` / `webhook` / `ci` |
| `parameters`    | object | Workflow-specific inputs     |

## Outputs

| Field            | Type    | Description                         |
|------------------|---------|-------------------------------------|
| `execution_id`   | string  | Unique run identifier               |
| `status`         | string  | `running` / `completed` / `failed`  |
| `step_results`   | array   | Per-step outcome details            |

## Integration Points

- Calls `card_platform_service` and `converter_service` REST APIs
- Delegates compliance checks to the **ComplianceAgent**
- Delegates security checks to the **SecurityAgent**
- Records all workflow events via the **LedgerAgent**
- References configuration in `foundry/schemas/platform.schema.json`

## Configuration

See `foundry/schemas/platform.schema.json` for the full configuration schema,
including workflow definitions, retry policies, and health-check intervals.
