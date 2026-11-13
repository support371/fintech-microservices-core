const express = require('express');
const { env } = require('./config/env');

const onboardingRoutes = require('./routes/onboarding.routes');
const automationRoutes = require('./routes/automation.routes');
const webhookRoutes = require('./routes/webhook.routes');

const app = express();

// Capture raw body buffer for exact webhook signature verification
app.use(
  express.json({
    verify: (req, _res, buf) => {
      req.rawBody = buf.toString('utf8');
    },
  })
);

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'healthy', service: 'striga-auto-btc' });
});

// Mount route modules
app.use('/api/onboarding', onboardingRoutes);
app.use('/api/automation', automationRoutes);
app.use('/webhooks', webhookRoutes);

// Start
app.listen(env.PORT, () => {
  console.log(`Striga Auto-BTC Backend running on port ${env.PORT}`);
  console.log(
    'Webhook endpoints ready at /webhooks/striga/ping and /webhooks/striga/tx'
  );
});

module.exports = app;
