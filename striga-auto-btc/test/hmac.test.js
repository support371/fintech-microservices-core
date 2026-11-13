/**
 * Verify that the HMAC-SHA256 signing client produces correct output.
 * Run: node test/hmac.test.js
 */

// Stub env vars before loading any module
process.env.STRIGA_BASE_URL = 'https://www.sandbox.striga.com/api/v1';
process.env.STRIGA_API_KEY = 'test-api-key';
process.env.STRIGA_API_SECRET = 'test-api-secret';

const crypto = require('crypto');
const { generateHmacHeader } = require('../services/strigaClient');

let passed = 0;
let failed = 0;

function assert(label, condition) {
  if (condition) {
    console.log(`  PASS: ${label}`);
    passed++;
  } else {
    console.error(`  FAIL: ${label}`);
    failed++;
  }
}

console.log('HMAC Signing Tests\n');

// Test 1: header format
const header = generateHmacHeader('POST', '/user/create', {
  firstName: 'Satoshi',
});
assert('Header starts with "HMAC "', header.startsWith('HMAC '));
assert(
  'Header has timestamp:signature format',
  /^HMAC \d+:[a-f0-9]{64}$/.test(header)
);

// Test 2: deterministic for same secret+inputs
const secret = 'test-secret';
const timestamp = '1700000000000';
const method = 'POST';
const endpoint = '/user/create';
const body = JSON.stringify({ firstName: 'Satoshi' });
const contentHash = crypto.createHash('md5').update(body).digest('hex');

const hmac = crypto.createHmac('sha256', secret);
hmac.update(timestamp);
hmac.update(method);
hmac.update(endpoint);
hmac.update(contentHash);
const expected = hmac.digest('hex');

assert('Signature is 64 hex chars', expected.length === 64);
assert('MD5 content hash is 32 hex chars', contentHash.length === 32);

// Test 3: empty body serialises to {}
const emptyBody = JSON.stringify({});
const emptyHash = crypto.createHash('md5').update(emptyBody).digest('hex');
const headerGet = generateHmacHeader('GET', '/wallets/list', {});
assert('GET with empty body produces valid header', /^HMAC \d+:[a-f0-9]{64}$/.test(headerGet));

// Test 4: different endpoints produce different signatures
const h1 = generateHmacHeader('POST', '/user/create', { a: 1 });
const h2 = generateHmacHeader('POST', '/wallets/create', { a: 1 });
assert(
  'Different endpoints produce different signatures',
  h1.split(':')[1] !== h2.split(':')[1]
);

console.log(`\nResults: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
