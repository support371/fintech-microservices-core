const express = require('express');
const { strigaRequest } = require('../services/strigaClient');

const router = express.Router();

/**
 * POST /api/onboarding/user
 * Create a user profile on Striga for KYC execution.
 */
router.post('/user', async (req, res) => {
  try {
    const { firstName, lastName, email, mobile, address, dateOfBirth } =
      req.body;

    const payload = {
      firstName: firstName || 'Satoshi',
      lastName: lastName || 'Nakamoto',
      email,
      mobile,
      address,
      dateOfBirth,
    };

    const user = await strigaRequest('POST', '/user/create', payload);
    res.status(201).json({ success: true, user });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.response?.data || err.message,
    });
  }
});

/**
 * POST /api/onboarding/provision-accounts
 * Create multi-currency wallet (fiat + BTC) and enrich with virtual banking details.
 */
router.post('/provision-accounts', async (req, res) => {
  try {
    const { userId, fiatCurrency = 'USD' } = req.body;

    if (!userId) {
      return res
        .status(400)
        .json({ success: false, error: 'userId is required' });
    }

    const wallet = await strigaRequest('POST', '/wallets/create', {
      userId,
      accountCurrency: [fiatCurrency, 'BTC'],
    });

    const fiatAccount = wallet.accounts[fiatCurrency];
    const btcAccount = wallet.accounts['BTC'];

    const enrichedFiat = await strigaRequest(
      'POST',
      '/wallets/account/enrich',
      { userId, accountId: fiatAccount.accountId }
    );

    const enrichedBtc = await strigaRequest(
      'POST',
      '/wallets/account/enrich',
      { userId, accountId: btcAccount.accountId }
    );

    res.status(200).json({
      success: true,
      walletId: wallet.walletId,
      fiatAccount: enrichedFiat,
      btcAccount: enrichedBtc,
    });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.response?.data || err.message,
    });
  }
});

module.exports = router;
