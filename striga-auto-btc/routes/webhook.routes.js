const express = require('express');
const crypto = require('crypto');
const { env } = require('../config/env');
const { logEvent, isDuplicate } = require('../database/ledger');

const router = express.Router();

/**
 * Middleware: verify Striga webhook signature using STRIGA_API_KEY.
 * Uses the raw body buffer captured by Express for exact byte-level matching.
 */
function verifyStrigaWebhook(req, res, next) {
  const incomingSig =
    req.headers['x-striga-signature'] || req.headers['signature'];

  if (!incomingSig) {
    return res
      .status(401)
      .json({ error: 'Missing webhook signature header' });
  }

  const rawPayload = req.rawBody || JSON.stringify(req.body);
  const expectedSig = crypto
    .createHmac('sha256', env.STRIGA_API_KEY)
    .update(rawPayload)
    .digest('hex');

  if (!crypto.timingSafeEqual(
    Buffer.from(incomingSig, 'hex'),
    Buffer.from(expectedSig, 'hex')
  )) {
    console.warn('[Webhook] Invalid Striga signature received.');
    return res.status(401).json({ error: 'Invalid webhook signature' });
  }

  next();
}

/**
 * POST /webhooks/striga/ping
 * Striga Dashboard test endpoint (no signature verification needed).
 */
router.post('/striga/ping', (req, res) => {
  console.log('[Striga Webhook Ping] Received:', req.body);
  res.status(200).json({ received: true });
});

/**
 * POST /webhooks/striga/tx
 * Transaction and standing order event listener.
 * Events are logged to the database ledger with idempotency checks.
 */
router.post('/striga/tx', verifyStrigaWebhook, async (req, res) => {
  const event = req.body;
  const txId = event.transactionId || event.id || '';

  console.log(
    `[Striga TX Event] Type: ${event.type} | TxID: ${txId}`
  );

  try {
    if (txId && (await isDuplicate(txId, event.type))) {
      console.log(`[Webhook] Duplicate event skipped: ${txId} / ${event.type}`);
      return res.status(200).json({ status: 'duplicate' });
    }

    switch (event.type) {
      case 'ACH_PAYIN_COMPLETED':
      case 'SEPA_PAYIN_COMPLETED':
      case 'FIAT_DEPOSIT_COMPLETED': {
        console.log(
          `-> Fiat pay-in settled for Account ${event.accountId}. Standing order executing...`
        );
        await logEvent({
          transaction_id: txId,
          event_type: event.type,
          account_id: event.accountId || '',
          amount: event.amount || null,
          currency: event.currency || '',
          status: 'FIAT_RECEIVED',
          raw_payload: event,
        });
        break;
      }

      case 'TRADE_EXECUTED':
      case 'SWAP_COMPLETED': {
        console.log(
          `-> Fiat converted to BTC! TxID: ${txId}`
        );
        await logEvent({
          transaction_id: txId,
          event_type: event.type,
          account_id: event.accountId || '',
          amount: event.btcAmount || event.amount || null,
          currency: 'BTC',
          exchange_rate: event.exchangeRate || null,
          status: 'SWAP_COMPLETED',
          raw_payload: event,
        });
        break;
      }

      case 'ONCHAIN_WITHDRAWAL_CONFIRMED': {
        console.log(
          `-> BTC swept on-chain! Hash: ${event.txHash || txId}`
        );
        await logEvent({
          transaction_id: txId,
          event_type: event.type,
          account_id: event.accountId || '',
          amount: event.amount || null,
          currency: 'BTC',
          tx_hash: event.txHash || '',
          status: 'SETTLED_ONCHAIN',
          raw_payload: event,
        });
        break;
      }

      case 'TRANSACTION_UNDER_REVIEW': {
        console.warn(
          `-> Compliance/Travel Rule hold on TxID: ${txId}`
        );
        await logEvent({
          transaction_id: txId,
          event_type: event.type,
          account_id: event.accountId || '',
          status: 'UNDER_REVIEW',
          raw_payload: event,
        });
        break;
      }

      default:
        console.log('-> Unhandled event:', JSON.stringify(event));
        await logEvent({
          transaction_id: txId,
          event_type: event.type || 'UNKNOWN',
          status: 'UNHANDLED',
          raw_payload: event,
        });
    }

    res.status(200).json({ status: 'processed' });
  } catch (err) {
    console.error('[Webhook Processing Error]:', err);
    res.status(500).json({ error: 'Internal processing error' });
  }
});

module.exports = router;
