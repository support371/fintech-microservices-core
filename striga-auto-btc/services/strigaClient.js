const crypto = require('crypto');
const axios = require('axios');
const { env } = require('../config/env');

/**
 * Generates the Striga v1 HMAC-SHA256 Authorization header.
 *
 * Signing payload: timestamp + METHOD + relativeEndpoint + md5(body)
 * Header format:   Authorization: HMAC <timestamp_ms>:<hex_signature>
 */
function generateHmacHeader(method, endpoint, body = {}) {
  const timestamp = Date.now().toString();
  const upperMethod = method.toUpperCase();

  const payloadString =
    body && Object.keys(body).length > 0
      ? JSON.stringify(body)
      : JSON.stringify({});

  const contentHash = crypto
    .createHash('md5')
    .update(payloadString)
    .digest('hex');

  const hmac = crypto.createHmac('sha256', env.STRIGA_API_SECRET);
  hmac.update(timestamp);
  hmac.update(upperMethod);
  hmac.update(endpoint);
  hmac.update(contentHash);

  const signature = hmac.digest('hex');
  return `HMAC ${timestamp}:${signature}`;
}

/**
 * Execute an authenticated request to the Striga v1 API.
 */
async function strigaRequest(method, endpoint, data = {}) {
  const authHeader = generateHmacHeader(method, endpoint, data);

  const config = {
    method: method.toLowerCase(),
    url: `${env.STRIGA_BASE_URL}${endpoint}`,
    headers: {
      'api-key': env.STRIGA_API_KEY,
      'Authorization': authHeader,
      'Content-Type': 'application/json',
    },
    timeout: 15000,
  };

  if (upperMethod(method) !== 'GET' && Object.keys(data).length > 0) {
    config.data = data;
  }

  try {
    const response = await axios(config);
    return response.data;
  } catch (error) {
    const errPayload = error.response ? error.response.data : error.message;
    console.error(
      `[Striga API Error] ${method.toUpperCase()} ${endpoint}:`,
      JSON.stringify(errPayload, null, 2)
    );
    throw error;
  }
}

function upperMethod(m) {
  return m.toUpperCase();
}

module.exports = { strigaRequest, generateHmacHeader };
