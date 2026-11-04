'use strict';
// Offline unit harness: no agent host, Codex binary, child process or HTTP.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { instrument, redactor } = require('../../ghcp_ahp_wire_preload.cjs');

const scenario = process.argv[2] || 'match';
const secret = 'SYNTHETIC_wire_secret_27/plus+quote"';
const records = [], nativeWrites = [], fetches = [], spawns = [], forks = [];
let response, lastChild;
const reply = { id: 'response-fixture', model: 'gpt-5.6-sol', reasoning: { effort: 'max' },
  usage: { input_tokens: 31, output_tokens: 2, output_tokens_details: { reasoning_tokens: 1 } },
  debugEcho: secret, account: { id: 'SYNTHETIC_ACCOUNT_73029' } };
if (scenario === 'mismatch_model') reply.model = 'gpt-5.6-sol-fast';
if (scenario === 'mismatch_effort') reply.reasoning.effort = 'high';
if (['missing', 'echo_only', 'headers_only', 'usage_only'].includes(scenario)) {
  delete reply.model; delete reply.reasoning;
}
if (scenario === 'usage_only') reply.usage.model = 'gpt-5.6-sol';
const nativeRequest = { id: 1, method: 'thread/start', params: { model: 'gpt-5.6-sol',
  config: { web_search: 'disabled', model_context_window: 1000000 }, approvalPolicy: 'untrusted' } };
const thread = { thread: { id: 'thread-fixture' }, model: 'gpt-5.6-sol', reasoningEffort: 'medium',
  approvalPolicy: 'untrusted', sandbox: { type: 'readOnly', networkAccess: false } };
const settings = { model: 'gpt-5.6-sol', effort: 'max', approvalPolicy: 'untrusted',
  sandboxPolicy: { type: 'readOnly', networkAccess: false } };

const hooks = instrument({
  fork(...args) { forks.push(args); return 'fake-child'; },
  spawn(command, args, settings) {
    spawns.push({ command, args, settings });
    const child = { stdin: { write(chunk) { nativeWrites.push(chunk); return false; },
      end(chunk) { if (chunk) nativeWrites.push(chunk); } }, stdout: new EventEmitter() };
    lastChild = child; return child;
  },
  async fetch(url, init) {
    fetches.push({ url, init });
    if (scenario === 'fetch_error') throw new Error('inert_fixture_failure');
    const event = data => `event: response.completed\r\ndata: ${JSON.stringify({ type: 'response.completed', response: data })}\r\n\r\n`;
    let text = event(reply);
    if (scenario === 'conflict') text += event({ ...reply, reasoning: { effort: 'high' } });
    if (scenario === 'truncated') text = text.slice(0, -4);
    if (scenario === 'plain') text = JSON.stringify(reply);
    const bytes = Buffer.from(text);
    response = new Response(new ReadableStream({ start(controller) {
      // One byte at a time: credential, Unicode and CRLF/SSE boundaries split.
      for (let at = 0; at < bytes.length; at++) controller.enqueue(bytes.subarray(at, at + 1));
      controller.close();
    } }), { status: scenario === 'http_error' ? 403 : 200,
      headers: { 'Content-Type': scenario === 'plain' ? 'application/json' : 'text/event-stream',
        'X-Request-Id': 'capi-request-fixture', 'Set-Cookie': secret,
        'X-Model': 'gpt-5.6-sol', 'X-Reasoning-Effort': 'max' } });
    return response;
  },
}, { emit: line => records.push(JSON.parse(line)), nativeBinary: '/fixture/codex', nativeSha256: 'a'.repeat(64),
  modelFree: scenario === 'model_free', synthetic: true, seeds: [secret],
  entrypoint: 'vs/platform/agentHost/node/agentHostMain',
  observerPath: '/fixture/observer.cjs', bootstrapForkPath: '/fixture/bootstrap-fork.js',
  verifyBinary() { if (scenario === 'binary_drift') throw new Error('wire_native_binary_drift'); } });

async function main() {
  if (scenario === 'fork') {
    const original = { execArgv: ['--fixture-flag'], env: { VSCODE_ESM_ENTRYPOINT: 'vs/platform/agentHost/node/agentHostMain' } };
    assert.equal(hooks.fork('/fixture/bootstrap-fork.js', ['--arg'], original), 'fake-child');
    assert.deepEqual(original.execArgv, ['--fixture-flag']);
    assert.deepEqual(forks[0][2].execArgv, ['--fixture-flag', '--require', '/fixture/observer.cjs']);
    assert.equal(forks[0][2].env.NODE_OPTIONS, undefined);
    assert.throws(() => hooks.fork('/wrong/bootstrap-fork.js', [], original), /wire_agent_fork_refused/);
    return;
  }
  if (scenario === 'redaction') {
    const mask = redactor([secret]);
    const body = { authorization: `Bearer ${secret}`, echo: secret, urlEcho: encodeURIComponent(secret),
      b64Echo: Buffer.from(secret).toString('base64'), input_tokens: 31, networkAccess: false };
    const clean = JSON.stringify(mask.clean(body));
    for (const token of [secret, encodeURIComponent(secret), Buffer.from(secret).toString('base64')]) assert(!clean.includes(token));
    assert(clean.includes('"input_tokens":31'));
    return;
  }
  if (scenario === 'unrelated') {
    hooks.spawn('/fixture/other', [], { env: { fixture: 'value' } });
    await hooks.fetch('https://example.invalid/models', {});
    assert.equal(records.length, 1);
    return;
  }
  if (scenario === 'binary_drift') {
    assert.throws(() => hooks.spawn('/fixture/codex', ['app-server'], {}), /wire_native_binary_drift/);
    assert.equal(spawns.length, 0); return;
  }
  const child = hooks.spawn('/fixture/codex', ['app-server', '-c', 'fixture=true'], {
    env: { PATH: '/fixture/bin', OPENAI_API_KEY: secret, NODE_OPTIONS: 'must-not-inherit', GHCP_AHP_WIRE_SEEDS: secret },
    stdio: ['pipe', 'pipe', 'pipe'] });
  assert.equal(lastChild, child);
  assert.equal(spawns[0].settings.env.NODE_OPTIONS, undefined);
  assert.equal(spawns[0].settings.env.GHCP_AHP_WIRE_SEEDS, undefined);
  assert.equal(spawns[0].settings.env.OPENAI_API_KEY, secret);
  if (scenario === 'model_free') {
    assert.throws(() => child.stdin.write(JSON.stringify({ id: 8, method: 'thread/start' })), /wire_model_free_partial_rpc_refused/);
    assert.throws(() => child.stdin.end(JSON.stringify({ id: 8, method: 'turn/start' })), /wire_model_free_partial_rpc_refused/);
    for (const method of ['thread/start', 'thread/resume', 'thread/fork', 'turn/start', 'account/login/start']) {
      assert.throws(() => child.stdin.write(JSON.stringify({ id: 10, method }) + '\n'), /wire_model_free_rpc_refused/);
    }
    assert.equal(nativeWrites.length, 0);
    await assert.rejects(hooks.fetch('https://api.githubcopilot.com/responses', { method: 'POST', body: '{}' }), /wire_model_free_http_refused/);
    assert.equal(fetches.length, 0); return;
  }
  const outgoing = JSON.stringify(nativeRequest) + '\n';
  assert.equal(child.stdin.write(outgoing), false); // Preserve backpressure.
  assert.equal(nativeWrites[0], outgoing);
  const incoming = JSON.stringify({ id: 1, result: thread }) + '\n';
    const observed = [];
  child.stdout.on('data', part => observed.push(part));
  for (const part of [incoming.slice(0, 3), incoming.slice(3)]) child.stdout.emit('data', Buffer.from(part));
  assert.equal(Buffer.concat(observed).toString(), incoming);
  child.stdin.write(JSON.stringify({ id: 2, method: 'turn/start', params: { threadId: 'thread-fixture', effort: 'max',
    collaborationMode: { settings: { reasoning_effort: 'max' } } } }) + '\n');
  child.stdout.emit('data', Buffer.from(JSON.stringify({ id: 2, result: { turn: { id: 'turn-fixture' } } }) + '\n'));
  child.stdout.emit('data', Buffer.from(JSON.stringify({ method: 'thread/settings/updated',
    params: { threadId: 'thread-fixture', threadSettings: settings } }) + '\n'));
  child.stdout.emit('data', Buffer.from(JSON.stringify({ method: 'thread/tokenUsage/updated',
    params: { threadId: 'thread-fixture', turnId: 'turn-fixture', tokenUsage: { modelContextWindow: 1000000 } } }) + '\n'));
  if (scenario === 'native_only') return;
  const init = { method: 'POST', headers: { Authorization: `Bearer ${secret}` },
    body: JSON.stringify({ model: 'gpt-5.6-sol', reasoning: { effort: 'max' }, input: 'CONNECTED', secret }),
    signal: new AbortController().signal };
  if (scenario === 'unsafe_endpoint') {
    await assert.rejects(hooks.fetch('https://example.invalid/responses', init), /wire_capi_transport_shape_refused/);
    assert.equal(fetches.length, 0); return;
  }
  if (scenario === 'fetch_error') {
    await assert.rejects(hooks.fetch('https://api.githubcopilot.com/responses', init), /inert_fixture_failure/);
    assert.equal(fetches.length, 1); return;
  }
  const actual = await hooks.fetch('https://api.githubcopilot.com/responses', init);
  assert.equal(actual, response);
  assert.equal(fetches.length, 1);
  assert.equal(fetches[0].init, init);
  if (scenario === 'echo_only') return; // No response consumption: no inferred response proof.
  if (scenario === 'plain') assert.equal(JSON.parse(await actual.text()).model, reply.model);
  else {
    const consume = async () => { const reader = actual.body.getReader(); while (!(await reader.read()).done) {} };
    if (scenario === 'truncated') await assert.rejects(consume(), /wire_truncated_frame/);
    else await consume();
  }
}

main().then(() => {
  const serialized = JSON.stringify(records);
  for (const token of [secret, encodeURIComponent(secret), Buffer.from(secret).toString('base64')]) assert(!serialized.includes(token));
  // Only already-redacted records leave this fake transport harness.
  process.stdout.write(serialized);
}).catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
