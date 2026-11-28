'use strict';
// No network, installed host or SDK. Only the metadata broker boundary is fake.
const assert = require('node:assert/strict');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const metadata = require('../../ghcp_ahp_metadata_client.cjs');
const scenario = process.argv[2];
const records = [], calls = [];
const secret = 'SYNTHETIC_METADATA_CREDENTIAL_NOT_REAL';
const hooks = instrument({ spawn() { throw Error('forbidden spawn'); }, fork() { throw Error('forbidden fork'); },
  fetch() { throw Error('original fetch bypassed Unix broker'); } }, {
  modelFree: true, sessionOnly: true, synthetic: true, nativeBinary: '/fake/codex', nativeSha256: 'a'.repeat(64),
  seeds: [secret], emit: line => records.push(JSON.parse(line)),
  async metadataRequest(message) {
    calls.push(message);
    if (scenario === 'broker_error') throw Error('synthetic broker refusal');
    return { status: scenario === 'status' ? 302 : 200, headers: { 'content-type': 'application/json' },
      body: Buffer.from('{"synthetic":true}'), external_request: true };
  },
});
async function main() {
  let url = metadata.USER_URL;
  const options = { method: 'GET', headers: { authorization: 'Bearer ' + secret } };
  if (scenario === 'models') url = 'https://api.individual.githubcopilot.com/models';
  if (scenario === 'post') options.method = 'POST';
  if (scenario === 'body') options.body = '{}';
  if (scenario === 'redirect') options.redirect = 'follow';
  if (scenario === 'responses') url = 'https://api.githubcopilot.com/responses';
  if (scenario === 'chat') url = 'https://api.githubcopilot.com/chat/completions';
  if (scenario === 'messages') url = 'https://api.githubcopilot.com/v1/messages';
  if (scenario === 'suffix') url = 'https://api.githubcopilot.com.evil.invalid/models';
  if (scenario === 'query') url += '?secret=' + secret;
  if (scenario === 'encoded') url = 'https://api.githubcopilot.com/%6dodels';
  if (scenario === 'path_alias') url = 'https://api.githubcopilot.com/x/../models';
  if (scenario === 'missing_auth') options.headers = {};
  if (['user', 'models'].includes(scenario)) {
    const response = await hooks.fetch(url, options);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { synthetic: true });
    assert.equal(calls.length, 1);
  } else {
    await assert.rejects(hooks.fetch(url, options), /metadata_/);
    assert.equal(calls.length, ['broker_error', 'status'].includes(scenario) ? 1 : 0);
    assert(records.some(row => row.kind === 'blocked'));
  }
  assert(!JSON.stringify(records).includes(secret));
  assert(!records.some(row => row.kind === 'capi_request'));
  process.stdout.write(JSON.stringify(records));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
