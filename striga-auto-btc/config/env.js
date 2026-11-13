require('dotenv').config();

const REQUIRED_VARS = [
  'STRIGA_BASE_URL',
  'STRIGA_API_KEY',
  'STRIGA_API_SECRET',
];

function validateEnv() {
  const missing = REQUIRED_VARS.filter((key) => !process.env[key]);
  if (missing.length > 0) {
    console.error(
      `[Config] Missing required environment variables: ${missing.join(', ')}`
    );
    process.exit(1);
  }
}

validateEnv();

const env = {
  PORT: parseInt(process.env.PORT || '3000', 10),
  STRIGA_BASE_URL: process.env.STRIGA_BASE_URL,
  STRIGA_API_KEY: process.env.STRIGA_API_KEY,
  STRIGA_API_SECRET: process.env.STRIGA_API_SECRET,
  DEFAULT_BTC_WHITELISTED_ADDRESS_ID:
    process.env.DEFAULT_BTC_WHITELISTED_ADDRESS_ID || '',
  DATABASE_URL: process.env.DATABASE_URL || '',
};

module.exports = { env };
