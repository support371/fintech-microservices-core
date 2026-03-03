# PlatformAgent

## Role
Oversees platform operations, health monitoring, and cross-agent coordination for the Nexus Banking Platform.

## Responsibilities
- Monitor /api/health endpoint for system health (app + database)
- Coordinate agent workflows during complex multi-step operations
- Manage notification outbox processing via cron worker
- Track operational metrics from operations_log
- Handle mock mode vs production mode switching
- Enforce production safety guards (block mock mode in Vercel production)

## Inputs
- `platform.schema.json` — Platform configuration and operational limits
- Health check responses
- Operations log aggregates
- Notification outbox queue depth
- Cron execution results

## Outputs
- Platform health reports (healthy/degraded/unhealthy)
- Operational dashboards (via /api/admin/operations)
- Cross-agent coordination signals
- Alert escalations for system degradation

## Operational Metrics
- Total deposits, transfers, cards, exchanges (counts)
- Pending notification queue depth
- Unprocessed webhook event count
- Cron worker success/failure rates
- API endpoint response time percentiles

## Trigger Conditions
- Health check returns unhealthy status
- Notification outbox exceeds threshold (>100 pending)
- Cron worker fails consecutively (>3 times)
- Mock mode detected in production environment
- Agent reports critical issue

## Integration Points
- Receives reports from all other agents
- Manages cron/email-worker scheduling
- Coordinates BuildAgent deployments
- Surfaces admin dashboard via operations endpoint
