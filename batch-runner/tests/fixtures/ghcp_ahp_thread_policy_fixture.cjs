'use strict';
// Only fake stdio/fetch. No Agent Host, native SDK or provider is executed.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const scenario = process.argv[2] || 'valid';
const records = [], writes = [], fetches = [], spawns = [];
let claims = 0, lastChild;
const args = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
  '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
const secret = 'SYNTHETIC_policy_token_12345';
const options = { emit: line => records.push(JSON.parse(line)), nativeBinary: '/fixture/codex',
  nativeSha256: 'a'.repeat(64), modelFree: true, sessionOnly: true, synthetic: true, seeds: [secret],
  entrypoint: 'vs/platform/agentHost/node/agentHostMain',
  claimThread() { if (claims++) throw new Error('already claimed'); } };
const transports = {
  fork() { throw new Error('not a fork test'); },
  spawn(command, argv, settings) {
    spawns.push({ command, argv });
    lastChild = { stdin: { write(value) { writes.push(value); return true; },
      end(value) { if (value) writes.push(value); } }, stdout: new EventEmitter() };
    return lastChild;
  },
  fetch(...values) { fetches.push(values); throw new Error('must not fetch'); },
};
const hooks = scenario === 'mode_mismatch' ? null : instrument(transports, options);
const request = { id: 2, method: 'thread/start', params: {
  model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy', approvalPolicy: 'untrusted',
  permissions: 'vscode-workspace-read-only', approvalsReviewer: 'user',
  config: { web_search: 'disabled', model_context_window: 1000000 }, dynamicTools: [] } };
const encode = value => JSON.stringify(value) + '\n';

async function main() {
  if (scenario === 'mode_mismatch') {
    assert.throws(() => instrument(transports, { ...options, modelFree: false }), /session_policy_mode_refused/);
    assert.equal(writes.length, 0); assert.equal(fetches.length, 0); assert.equal(spawns.length, 0);
    return;
  }
  if (scenario.startsWith('http_')) {
    const url = { http_response: 'https://api.githubcopilot.com/responses',
      http_models: 'https://api.githubcopilot.com/models', http_auth: 'https://api.github.com/copilot_internal/v2/token',
      http_local: 'http://127.0.0.1:42/private', http_other: 'https://example.invalid/a' }[scenario];
    await assert.rejects(hooks.fetch(url, { method: 'GET', headers: { authorization: secret } }), /session_policy_http_refused/);
    assert.equal(fetches.length, 0); return;
  }
  if (scenario === 'launch_wrong' || scenario === 'launch_duplicate') {
    if (scenario === 'launch_wrong') args[2] = 'model="gpt-5.6-sol-fast"';
    else args.push('-c', 'model_reasoning_effort="max"');
    assert.throws(() => hooks.spawn('/fixture/codex', args, {}), /session_policy_launch_config_refused/);
    assert.equal(spawns.length, 0); return;
  }
  const child = hooks.spawn('/fixture/codex', args, { env: { OPENAI_API_KEY: secret } });
  assert.equal(spawns.length, 1);
  if (scenario === 'bad_model') request.params.model = 'gpt-5.6-sol-fast';
  if (scenario === 'bad_provider') request.params.modelProvider = 'openai';
  if (scenario === 'bad_approval') request.params.approvalPolicy = 'never';
  if (scenario === 'bad_permissions') request.params.permissions = 'vscode-workspace';
  if (scenario === 'bad_web') request.params.config.web_search = 'live';
  if (scenario === 'bad_context') request.params.config.model_context_window = '1000000';
  if (scenario === 'bad_effort') request.params.config.model_reasoning_effort = 'xhigh';
  if (scenario === 'bad_fallback') request.params.allowProviderModelFallback = true;
  if (scenario === 'bad_mcp') request.params.config.mcp_servers = { unapproved: {} };
  if (scenario === 'bad_reply') request.result = {};
  if (scenario === 'bad_catalog_default') request.params.model = 'gpt-5.3-codex';
  if (scenario === 'bad_missing_model') delete request.params.model;
  if (scenario === 'bad_null_model') request.params.model = null;
  if (scenario === 'bad_no_params') delete request.params;
  if (scenario === 'bad_null_params') request.params = null;
  if (scenario === 'bad_no_config') delete request.params.config;
  if (scenario === 'bad_null_config') request.params.config = null;
  if (scenario === 'bad_both_permissions') request.params.sandbox = 'read-only';
  if (scenario === 'bad_null_sandbox') request.params.sandbox = null;
  if (scenario === 'bad_numeric_context') request.params.config.model_context_window = 922000;
  if (scenario === 'bad_null_context') request.params.config.model_context_window = null;
  if (scenario === 'bad_null_effort') request.params.config.model_reasoning_effort = null;
  if (scenario === 'bad_null_fallback') request.params.allowProviderModelFallback = null;
  if (scenario === 'bad_id') request.id = true;
  if (scenario === 'bad_no_id') delete request.id;
  if (scenario === 'bad_error') request.error = { message: secret };
  if (scenario === 'bad_multiple') {
    request.params.model = 'gpt-5.3-codex';
    request.params.approvalPolicy = 'on-request';
    request.params.config.model_context_window = 922000;
  }
  if (scenario === 'bad_diagnostic_secret') request.params.model = secret;
  if (scenario === 'bad_diagnostic_encoded') request.params.model = Buffer.from(secret).toString('base64');
  if (scenario === 'bad_diagnostic_object') request.params.model = { token: secret, prompt: 'PRIVATE_FIXTURE' };
  if (scenario === 'bad_diagnostic_long') request.params.model = 'x'.repeat(300) + secret;
  if (scenario === 'valid_sandbox') {
    delete request.params.permissions;
    request.params.sandbox = 'read-only';
  }
  if (scenario === 'valid_optional_omitted') delete request.params.config.model_context_window;
  if (scenario === 'valid_optional_exact') {
    request.params.config.model_reasoning_effort = 'max';
    request.params.config.mcp_servers = {};
    request.params.allowProviderModelFallback = false;
  }
  if (scenario.startsWith('bad_')) {
    assert.throws(() => child.stdin.write(encode(request)), /session_policy_thread_contract_refused/);
    assert.equal(writes.length, 0);
    assert.equal(fetches.length, 0);
    assert.equal(claims, 0);
    const refusal = records.find(row => row.reason === 'session_policy_thread_contract_refused');
    assert(refusal.rejections.length > 0);
    assert.deepEqual(refusal.rejected_fields, refusal.rejections.map(row => row.field));
    for (const rejection of refusal.rejections) {
      assert.deepEqual(Object.keys(rejection).sort(), ['actual', 'expected', 'field']);
    }
    assert(!JSON.stringify(records).includes('PRIVATE_FIXTURE'));
    return;
  }
  if (['turn', 'resume', 'fork', 'exec', 'reply', 'partial', 'batch', 'end'].includes(scenario)) {
    const method = { turn: 'turn/start', resume: 'thread/resume', fork: 'thread/fork', exec: 'command/exec' }[scenario] || 'turn/start';
    const value = scenario === 'reply' ? { id: 9, result: { approved: true } } : { id: 9, method, params: {} };
    let payload = encode(value);
    if (scenario === 'partial' || scenario === 'end') payload = payload.trimEnd();
    if (scenario === 'batch') payload = encode(request) + payload;
    assert.throws(() => scenario === 'end' ? child.stdin.end(payload) : child.stdin.write(payload), /wire_model_free_/);
    assert.equal(writes.length, 0); return;
  }
  if (scenario === 'claim_used') claims = 1;
  if (scenario === 'claim_used') {
    assert.throws(() => child.stdin.write(encode(request)), /session_policy_thread_limit/);
    assert.equal(writes.length, 0); return;
  }
  child.stdin.write(encode(request));
  assert.equal(writes[0], encode(request));
  child.stdout.emit('data', Buffer.from(encode({ id: 2, result: { thread: { id: 'owned-thread' },
    model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy', approvalPolicy: 'untrusted',
    sandbox: { type: 'readOnly', networkAccess: false }, reasoningEffort: 'max' } })));
  if (scenario === 'duplicate') {
    assert.throws(() => child.stdin.write(encode({ ...request, id: 3 })), /session_policy_thread_limit/);
    assert.equal(writes.length, 1); return;
  }
  if (scenario === 'second_process') {
    const second = instrument(transports, options).spawn('/fixture/codex', args, {});
    assert.throws(() => second.stdin.write(encode(request)), /session_policy_thread_limit/);
    assert.equal(writes.length, 1); return;
  }
  if (scenario === 'incoming_turn' || scenario === 'incoming_tool') {
    assert.throws(() => child.stdout.emit('data', Buffer.from(encode({ method: scenario === 'incoming_turn' ?
      'turn/started' : 'item/tool/call', params: {} }))), /session_policy_turn_or_tool_refused/);
    return;
  }
  const cleanup = { id: 4, method: 'thread/unsubscribe', params: { threadId: 'owned-thread' } };
  if (scenario === 'foreign_cleanup') {
    cleanup.params.threadId = 'not-ours';
    assert.throws(() => child.stdin.write(encode(cleanup)), /session_policy_foreign_cleanup_refused/);
    assert.equal(writes.length, 1); return;
  }
  child.stdin.write(encode(cleanup));
  assert.equal(writes.length, 2);
  assert.equal(fetches.length, 0);
}
main().then(() => {
  assert(!JSON.stringify(records).includes(secret));
  process.stdout.write(JSON.stringify(records));
}).catch(error => { console.error(error); process.exitCode = 1; });
