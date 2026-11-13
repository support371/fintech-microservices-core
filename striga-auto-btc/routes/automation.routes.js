const express = require('express');
const { strigaRequest } = require('../services/strigaClient');
const { env } = require('../config/env');

const router = express.Router();

/**
 * POST /api/automation/standing-order
 * Create an automated fiat-to-BTC conversion standing order.
 * Returns an SCA challengeId that must be confirmed with OTP.
 */
router.post('/standing-order', async (req, res) => {
  try {
    const {
      userId,
      sourceFiatAccountId,
      action = 'SWAP_AND_WITHDRAW',
      whitelistedAddressId = env.DEFAULT_BTC_WHITELISTED_ADDRESS_ID,
      verificationMethod = 'sms',
    } = req.body;

    if (!userId || !sourceFiatAccountId) {
      return res.status(400).json({
        success: false,
        error: 'userId and sourceFiatAccountId are required',
      });
    }

    const payload = {
      uuid: userId,
      accountId: sourceFiatAccountId,
      action,
      verificationMethod,
    };

    if (action === 'SWAP_AND_WITHDRAW') {
      if (!whitelistedAddressId) {
        return res.status(400).json({
          success: false,
          error:
            'whitelistedAddressId is required for SWAP_AND_WITHDRAW action',
        });
      }
      payload.whitelistedAddressId = whitelistedAddressId;
    } else if (action === 'SWAP_ONLY') {
      payload.destinationCurrency = 'BTC';
    } else {
      return res.status(400).json({
        success: false,
        error: 'action must be SWAP_AND_WITHDRAW or SWAP_ONLY',
      });
    }

    const challenge = await strigaRequest('POST', '/standing-orders', payload);
    res.status(201).json({
      success: true,
      message:
        'Standing order created. Confirm challengeId with OTP to activate.',
      challenge,
    });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.response?.data || err.message,
    });
  }
});

/**
 * POST /api/automation/standing-order/confirm
 * Confirm the standing order via SCA OTP verification.
 */
router.post('/standing-order/confirm', async (req, res) => {
  try {
    const { userId, challengeId, verificationCode } = req.body;

    if (!userId || !challengeId || !verificationCode) {
      return res.status(400).json({
        success: false,
        error: 'userId, challengeId, and verificationCode are required',
      });
    }

    const confirmation = await strigaRequest(
      'POST',
      '/standing-orders/confirm',
      {
        uuid: userId,
        challengeId,
        verificationCode,
      }
    );

    res.status(200).json({
      success: true,
      message: 'Auto-BTC Standing Order is now ACTIVE.',
      standingOrder: confirmation,
    });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.response?.data || err.message,
    });
  }
});

module.exports = router;
