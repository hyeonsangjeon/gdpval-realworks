'use strict';
// Inert stdio only. Reproduce the pinned catalog/write-error/dispose sequence,
// never execute VS Code, the SDK, a hook, a native process or network request.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const scenario = process.argv[2];
const records = [], writes = [], ends = [];
let spawnCount = 0;
const secret = 'SYNTHETIC_RPC_PRIVATE_seed_12345';
const encode = value => JSON.stringify(value) + '\n';
const launch = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
  '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
const hooks = instrument({
  fork() { assert.fail('fixture must not fork'); },
  fetch() { assert.fail('fixture must not fetch'); },
  spawn() {
    ++spawnCount;
    return { stdin: { write(chunk) { writes.push(chunk); return true; }, end(chunk) { ends.push(chunk); } },
      stdout: new EventEmitter() };
  },
}, { emit: line => records.push(JSON.parse(line)), nativeBinary: '/fixture/codex',
  nativeSha256: 'a'.repeat(64), modelFree: true, sessionOnly: !['capability', 'pinned_disconnect'].includes(scenario),
  synthetic: true, seeds: [secret], entrypoint: 'vs/platform/agentHost/node/agentHostMain' });
const child = hooks.spawn('/fixture/codex', launch, { env: { OPENAI_API_KEY: secret } });
const deny = (operation, reason = 'wire_model_free_rpc_refused') => assert.throws(operation, { message: reason });
const prelude = ['initialize', 'initialized', 'mcpServerStatus/list', 'account/read', 'config/read',
  'account/read', 'config/read', 'model/list', 'skills/list'];

if (scenario === 'pinned_disconnect') {
  // VS Code 2c33b50b codexAgent.ts:8569/8589 starts these catalog requests.
  prelude.forEach((method, index) => child.stdin.write(encode({ method,
    ...(method === 'initialized' ? {} : { id: index + 1 }), params: {} })));
  // codexAppServerClient.ts:350/353 -> codexAgent.ts:2762/4689 -> :451 EOF.
  // Reproduce the old sequence in capability-only mode: the new permission is
  // session-only. EOF must still refuse but must not count this frame twice.
  deny(() => child.stdin.write(encode({ id: 10, method: 'hooks/list', params: { cwds: ['/fixture/workspace'] } })));
  deny(() => child.stdin.end());
  assert.equal(writes.length, prelude.length);
} else if (scenario === 'multi_stream') {
  deny(() => child.stdin.write(encode({ id: 1, method: 'hooks/list' })), 'wire_hooks_list_contract_refused');
  const second = hooks.spawn('/fixture/codex', launch, { env: { OPENAI_API_KEY: secret } });
  deny(() => second.stdin.write(encode({ id: 1, method: 'config/batchWrite' })));
} else if (scenario === 'batch') {
  deny(() => child.stdin.write(encode({ id: 1, method: 'initialize' }) +
    encode({ id: 2, method: 'hooks/list' }) + encode({ id: 3, method: 'turn/start' })), 'wire_hooks_list_contract_refused');
} else {
  const request = { id: 'PRIVATE_FIXTURE_id', method: 'hooks/list',
    params: { token: secret, nested: { input: 'PRIVATE_FIXTURE_prompt', cwd: '/PRIVATE_FIXTURE/path' } } };
  const methods = { turn: 'turn/start', resume: 'thread/resume', fork: 'thread/fork',
    login: 'account/login/start', write: 'config/batchWrite', exec: 'command/exec',
    fs_write: 'fs/writeFile', hooks: 'hooks/list', capability: 'hooks/list', end_chunk: 'hooks/list' };
  if (Object.hasOwn(methods, scenario)) request.method = methods[scenario];
  else if (scenario === 'result' || scenario === 'error') {
    request.method = 'config/read'; request[scenario] = { secret, data: 'PRIVATE_FIXTURE_response' };
  } else if (scenario === 'missing') delete request.method;
  else if (scenario === 'null') request.method = null;
  else if (scenario === 'object') request.method = { secret, data: 'PRIVATE_FIXTURE_object' };
  else if (scenario === 'array') request.method = [secret];
  else if (scenario === 'number') request.method = 17;
  else if (scenario === 'boolean') request.method = false;
  else if (scenario === 'long') request.method = secret.repeat(20);
  else if (scenario === 'secret') request.method = secret;
  else if (scenario === 'encoded') request.method = Buffer.from(secret).toString('base64');
  else if (scenario === 'token_shape') request.method = 'ghp_SYNTHETIC_ONLY_NOT_A_CREDENTIAL_12345';
  else assert.fail('unknown fixture scenario');
  deny(() => scenario === 'end_chunk' ? child.stdin.end(encode(request)) : child.stdin.write(encode(request)),
    ['hooks', 'end_chunk'].includes(scenario) ? 'wire_hooks_list_contract_refused' : 'wire_model_free_rpc_refused');
}
assert.equal(ends.length, 0);
if (scenario !== 'pinned_disconnect') assert.equal(writes.length, 0);
assert(!JSON.stringify(records).includes(secret));
assert(!JSON.stringify(records).includes('PRIVATE_FIXTURE'));
process.stdout.write(JSON.stringify({ records, spawnCount, underlying_ends: ends.length,
  forwarded_methods: writes.map(text => JSON.parse(text).method), real_processes: 0, external_requests: 0 }));
