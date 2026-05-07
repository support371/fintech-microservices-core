# User Guide

## Overview

The Fintech Microservices Platform enables secure cryptocurrency debit card operations, including account onboarding, fund loading, and currency conversion with full regulatory compliance.

## Account Onboarding

### KYC Verification

Before using any platform services, users must complete KYC (Know Your Customer) verification:

1. **Tier 1**: Basic identity verification (name, email, phone)
2. **Tier 2**: Enhanced verification (government ID, proof of address)
3. **Tier 3**: Full verification (all Tier 2 + additional compliance checks)

> **Note**: Card issuance and fund operations require **Tier 3** or higher KYC status.

### Requesting a Crypto Debit Card

Once KYC Tier 3 is achieved:

```
POST /api/v1/cards/issue
Content-Type: application/json

{
  "user_id": "user-12345",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Success Response** (200):
```json
{
  "status": "Card Issued",
  "card_id": "card-user-12345-123"
}
```

**KYC Not Approved** (403):
```json
{
  "detail": "KYC status is Tier 2. Requires Tier 3."
}
```

## Fund Loading

### Loading Fiat Funds (Triggers BTC Conversion)

```
POST /api/v1/funds/load
Content-Type: application/json

{
  "user_id": "user-12345",
  "fiat_amount": 1000.00,
  "fiat_currency": "USD"
}
```

**Success Response** (200):
```json
{
  "status": "Conversion Initiated",
  "details": {
    "btc_amount_sent": 0.01428571,
    "satoshis_sent": 1428571,
    "exchange_rate_used": 70000.0,
    "fiat_currency": "USD",
    "success_time": "2026-03-04T10:30:00.000000"
  }
}
```

### Supported Currencies

| Currency | Code |
|----------|------|
| US Dollar | USD |
| Euro | EUR |
| British Pound | GBP |

### Transaction Limits

| Limit Type | Default Value |
|------------|---------------|
| Single Transaction | $10,000 |
| Daily Cumulative | $50,000 |
| Monthly Cumulative | $200,000 |

> Transactions exceeding these limits will be flagged for AML review.

## Currency Conversion

When fiat funds are loaded, the system automatically:

1. Validates the user's KYC status
2. Checks AML transaction limits
3. Initiates fiat-to-BTC conversion via the Striga API
4. Sends converted BTC to the user's wallet
5. Logs the transaction for audit purposes

The conversion uses real-time exchange rates from the Striga platform.

## Error Handling

### Common Error Codes

| HTTP Code | Meaning | Action Required |
|-----------|---------|-----------------|
| 400 | Bad Request | Check request payload format |
| 403 | Forbidden | Verify KYC tier meets minimum requirements |
| 415 | Unsupported Media Type | Use `Content-Type: application/json` |
| 500 | Internal Server Error | Contact support; the system will retry automatically |
| 503 | Service Unavailable | The conversion service is temporarily down; retry later |

### Webhook Events

The platform receives webhook notifications from the Striga payment platform:

- **`fiat_received`**: Triggered when a fiat deposit is confirmed
- Webhooks are validated using HMAC-SHA256 signature verification
- Duplicate events are handled through idempotency checks

## Compliance Verification

### AML Monitoring

All transactions are monitored against AML thresholds:
- Transactions exceeding single-transaction limits are flagged
- Daily and monthly cumulative limits are enforced
- Suspicious activity triggers automated alerts

### Audit Trail

Every financial operation generates an audit log entry containing:
- Timestamp
- User ID
- Transaction ID (with trace ID for cross-service tracking)
- Action performed
- Result (success/failure)
- Compliance flags

Audit logs are retained for **5 years** per regulatory requirements.

## GEM Dashboard

The web dashboard provides:

- **Deposit Management**: View and create deposits
- **Card Operations**: View card status and details
- **Balance Overview**: Real-time balance and BTC holdings
- **Admin Dashboard**: Operations monitoring and management (admin users only)

### Accessing the Dashboard

Navigate to the deployed dashboard URL in your browser. The dashboard requires authentication and displays different views based on user role.

## Support

For technical issues:
1. Check the [Deployment Guide](./deployment-guide.md) for system status
2. Review error codes in the table above
3. Contact the engineering team for unresolved issues
