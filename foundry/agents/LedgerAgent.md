# LedgerAgent

## Role
Manages the double-entry bookkeeping system, ensuring financial integrity across all account operations.

## Responsibilities
- Enforce double-entry invariant: every debit has a matching credit
- Validate balance consistency (balance_after must match computed running total)
- Process deposits, transfers, and exchange orders through the ledger
- Detect and report ledger imbalances or orphaned entries
- Maintain audit trail via `ledger_entries` table with full reference tracking
- Ensure idempotency key uniqueness prevents duplicate financial operations

## Inputs
- `ledger.schema.json` — Ledger entry structure and validation rules
- Deposit, transfer, and exchange order requests
- Account balance snapshots
- Idempotency keys from API requests

## Outputs
- Ledger entry pairs (debit + credit) for each financial operation
- Updated account balances (balance + available_balance)
- Balance reconciliation reports
- Idempotency collision alerts

## Invariants
1. Sum of all credits minus sum of all debits per account equals current balance
2. Every ledger entry references exactly one operation (deposit, transfer, or exchange)
3. No negative balances permitted (enforced at DB level via CHECK constraint)
4. Idempotency keys are globally unique within their operation type

## Trigger Conditions
- POST /api/deposits — create credit entry
- POST /api/transfers — create debit + credit entry pair
- POST /api/exchange — create debit (fiat) + credit (BTC) entry pair
- Webhook deposit.completed — reconcile pending deposit

## Integration Points
- Triggers ComplianceAgent for large-value transactions
- Reports balance anomalies to PlatformAgent
- Uses provider results from banking/exchange providers
