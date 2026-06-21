# Nexus Gateway Integration

The product-facing Nexus API must act as a backend-for-frontend. Browser code must never receive provider credentials, database credentials, webhook secrets, internal service secrets, or future card/payment provider keys.

## Current approved integration scope

The Nexus application may read the core gateway and service health endpoints to display system status.

Financial write routes are not approved for exposure through the Nexus API until the Python card service enforces `NEXUS_GATEWAY_API_KEY` (or an equivalent authenticated user/session design) on every card and funding endpoint.

## Safety rules

- Keep `PAYMENTS_MODE=sandbox`.
- Keep `CARD_ISSUANCE_MODE=sandbox`.
- Keep both live-approval flags disabled.
- Do not proxy `/internal/*` or `/webhook/*` through the browser-facing application.
- Do not place any core secret in `app/config.js`, HTML, or a `NEXT_PUBLIC_*` variable.
- Treat health responses as untrusted upstream data and apply timeouts.
