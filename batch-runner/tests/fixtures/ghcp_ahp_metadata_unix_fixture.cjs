'use strict';
const assert = require('node:assert/strict');
const { client, USER_URL } = require('../../ghcp_ahp_metadata_client.cjs');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const token = 'SYNTHETIC_AuthZeroTurn_NotACredential_123456';
const rows = [];
const forbidden = () => { throw Error('real process/fetch forbidden'); };
const hooks = instrument({ spawn: forbidden, fork: forbidden, fetch: forbidden }, {
  nativeBinary: '/fake/codex', nativeSha256: 'a'.repeat(64), modelFree: true, sessionOnly: true, synthetic: true,
  seeds: [token], emit: line => rows.push(JSON.parse(line)), metadataRequest: client(process.argv[2]),
});
(async () => {
  const options = { method: 'GET', headers: { authorization: 'Bearer ' + token, accept: 'application/json' } };
  const discovered = await (await hooks.fetch(USER_URL, options)).json();
  const models = await (await hooks.fetch(discovered.endpoints.api + '/models', options)).json();
  assert.equal(models.data[0].id, 'gpt-5.6-sol');
  assert(!JSON.stringify(rows).includes(token));
  process.stdout.write(JSON.stringify(rows));
})().catch(error => { console.error(error); process.exitCode = 1; });
