'use strict';
// Fake stdio and responses only: no SDK, host, hook, native process or network.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const scenario = process.argv[2];
const records = [], writes = [], ends = [], responseBytes = [];
const secret = 'SYNTHETIC_hooks_secret_67890';
const root = '/fixture/owned', workspace = root + '/workspace';
const encode = value => JSON.stringify(value) + '\n';
const launch = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
  '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
const forkContract = { schema_version: 'ghcp-ahp-agent-fork-v1', state_root: root };
if (scenario === 'root_missing') delete forkContract.state_root;
if (scenario === 'root_relative') forkContract.state_root = 'relative';
if (scenario === 'root_dotdot') forkContract.state_root = '/fixture/a/../owned';
if (scenario === 'root_broad') forkContract.state_root = '/';
if (scenario === 'root_schema') forkContract.schema_version = 'unknown';
const hooks = instrument({
  fork() { assert.fail('must not fork'); }, fetch() { assert.fail('must not fetch'); },
  spawn() {
    return { stdin: { write(chunk) { writes.push(chunk); return true; }, end(chunk) { if (chunk) writes.push(chunk); ends.push(true); } },
      stdout: new EventEmitter() };
  },
}, { emit: line => records.push(JSON.parse(line)), nativeBinary: '/fixture/codex', nativeSha256: 'a'.repeat(64),
  modelFree: true, sessionOnly: scenario !== 'capability', synthetic: true, seeds: [secret], forkContract,
  entrypoint: 'vs/platform/agentHost/node/agentHostMain' });
const child = hooks.spawn('/fixture/codex', launch, { env: { OPENAI_API_KEY: secret } });
const request = { id: 10, method: 'hooks/list', params: { cwds: [workspace] } };
const good = new Set(['valid', 'prelude', 'distinct', 'end_chunk', 'fragmented', 'jsonrpc', 'string_id',
  'error_response', 'invalid_response', 'missing_response']);
let reason;
const send = message => {
  const text = encode(message);
  assert.equal(child.stdin.write(text), true);
  assert.equal(writes.at(-1), text); // Redaction never changes transport bytes.
};
const reply = id => {
  let response = { id, result: { data: [{ cwd: workspace, hooks: [
    { eventName: 'SessionStart', handlerType: 'command', command: 'never execute ' + secret, enabled: true },
    { eventName: 'Stop', handlerType: 'prompt', statusMessage: '한글 🔒 ' + secret }],
    warnings: [], errors: [], token: secret }] } };
  if (scenario === 'error_response') response = { id, error: { code: -32602, message: secret } };
  if (scenario === 'invalid_response') response = { id, result: { data: 'not-an-array' } };
  const bytes = Buffer.from(encode(response));
  responseBytes.push(bytes.length);
  if (scenario === 'fragmented') for (const byte of bytes) child.stdout.emit('data', Buffer.from([byte]));
  else child.stdout.emit('data', bytes);
};

if (good.has(scenario)) {
  if (scenario === 'prelude') ['initialize', 'initialized', 'mcpServerStatus/list', 'account/read', 'config/read',
    'account/read', 'config/read', 'model/list', 'skills/list'].forEach((method, index) => send({ method,
      ...(method === 'initialized' ? {} : { id: index + 1 }), params: {} }));
  if (scenario === 'jsonrpc') request.jsonrpc = '2.0';
  if (scenario === 'string_id') request.id = 'public-fixture-id';
  if (scenario === 'end_chunk') {
    child.stdin.end(encode(request));
    assert.equal(writes.at(-1), encode(request));
  } else send(request);
  if (scenario !== 'missing_response') reply(request.id);
  if (scenario === 'distinct') { send({ ...request, id: 11 }); reply(11); }
  if (scenario !== 'end_chunk') child.stdin.end();
  assert.equal(ends.length, 1);
} else if (scenario === 'latched') {
  const forbidden = encode({ id: 10, method: 'hooks/run', params: { command: secret } });
  let first;
  try { child.stdin.write(forbidden); assert.fail('must refuse'); } catch (error) { first = error; }
  assert.equal(first.message, 'wire_model_free_rpc_refused');
  assert.throws(() => child.stdin.end(), error => error === first);
  assert.throws(() => send(request), error => error === first);
  reason = first.message;
} else if (scenario === 'batch') {
  assert.throws(() => child.stdin.write(encode(request) + encode({ id: 11, method: 'turn/start', params: {} })),
    { message: 'wire_model_free_rpc_refused' });
  reason = 'wire_model_free_rpc_refused';
} else {
  const methods = { run: 'hooks/run', execute: 'hooks/execute', register: 'hooks/register',
    update: 'hooks/update', write: 'hooks/write', remove: 'hooks/remove', configure: 'hooks/config/write',
    singular: 'hook/list', suffix: 'hooks/listAll', trailing_slash: 'hooks/list/', prefix: 'other/hooks/list',
    case: 'Hooks/list', whitespace: 'hooks/list ', encoded: 'hooks%2Flist', nul: 'hooks/list\u0000',
    unknown: 'unknown/list', turn: 'turn/start' };
  if (Object.hasOwn(methods, scenario)) request.method = methods[scenario];
  else if (scenario === 'params_missing') delete request.params;
  else if (scenario === 'params_null') request.params = null;
  else if (scenario === 'params_array') request.params = [];
  else if (scenario === 'params_string') request.params = secret;
  else if (scenario === 'params_empty') request.params = {};
  else if (scenario === 'extra_command') request.params.command = secret;
  else if (scenario === 'extra_run') request.params.run = true;
  else if (scenario === 'extra_register') request.params.register = {};
  else if (scenario === 'cwds_empty') request.params.cwds = [];
  else if (scenario === 'cwds_null') request.params.cwds = null;
  else if (scenario === 'cwds_string') request.params.cwds = workspace;
  else if (scenario === 'cwds_many') request.params.cwds = [workspace, workspace];
  else if (scenario === 'cwd_object') request.params.cwds = [{ token: secret }];
  else if (scenario === 'cwd_null') request.params.cwds = [null];
  else if (scenario === 'cwd_number') request.params.cwds = [10];
  else if (scenario === 'cwd_other') request.params.cwds = ['/fixture/other'];
  else if (scenario === 'cwd_relative') request.params.cwds = ['workspace'];
  else if (scenario === 'cwd_dotdot') request.params.cwds = [root + '/other/../workspace'];
  else if (scenario === 'id_missing') delete request.id;
  else if (scenario === 'id_null') request.id = null;
  else if (scenario === 'id_bool') request.id = true;
  else if (scenario === 'id_fraction') request.id = 1.5;
  else if (scenario === 'id_negative') request.id = -1;
  else if (scenario === 'id_empty') request.id = '';
  else if (scenario === 'id_long') request.id = secret.repeat(20);
  else if (scenario === 'result' || scenario === 'error') request[scenario] = { token: secret };
  else if (scenario === 'jsonrpc_wrong') request.jsonrpc = '1.0';
  else if (scenario === 'envelope_extra') request.execute = true;
  else assert(['capability', 'root_missing', 'root_relative', 'root_dotdot', 'root_broad', 'root_schema'].includes(scenario));
  reason = request.method === 'hooks/list' && scenario !== 'capability' ? 'wire_hooks_list_contract_refused' : 'wire_model_free_rpc_refused';
  assert.throws(() => send(request), { message: reason });
  assert.throws(() => child.stdin.end(), { message: reason });
}
if (!good.has(scenario)) { assert.equal(writes.length, 0); assert.equal(ends.length, 0); }
assert(!JSON.stringify(records).includes(secret));
if (good.has(scenario)) assert(!JSON.stringify(records).includes(workspace));
process.stdout.write(JSON.stringify({ records, response_bytes: responseBytes, refusal_reason: reason,
  forwarded_methods: writes.map(text => JSON.parse(text).method), underlying_ends: ends.length,
  real_processes: 0, external_requests: 0 }));
