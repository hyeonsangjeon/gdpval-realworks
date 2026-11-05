'use strict';
// Only the upstream child IPC service is fake. Real codec, transaction,
// one-use state machine and response routing are exercised without a model.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL, fileURLToPath } = require('node:url');
const bridge = require('../../ghcp_ahp_management_bridge.cjs');
const session = 'ahp-session:/12345678-1234-4234-8234-123456789abc';
let workspace = 'file:///tmp/fixture%20owned/workspace';
const clone = v => JSON.parse(JSON.stringify(v));

class FakeChild extends EventEmitter {
  constructor(mode) { super(); this.mode = mode; this.connected = true; this.sent = []; }
  send(raw, callback) {
    const request = bridge.decode(raw); this.sent.push(request);
    const [type, id, channel, command] = request.header;
    assert.equal(type, 100);
    if (this.mode === 'lost_reply') { callback?.(); return true; }
    let response, code = 201;
    if (command === 'resolveSessionConfig') {
      assert.equal(channel, 'agentHost');
      assert.deepEqual(request.body, [{ provider: 'codex', config: bridge.POLICY,
        workingDirectory: { $mid: 1, scheme: 'file', authority: '', path: fileURLToPath(workspace), query: '', fragment: '' } }]);
      response = { values: { ...bridge.POLICY, mode: 'interactive', isolation: 'folder' }, schema: {} };
      const bad = {
        approval: ['codex.approvalPolicy', 'on-request'], sandbox: ['codex.sandboxMode', 'workspace-write'],
        preset: ['codex.permissionsPreset', 'default'], network: ['codex.networkAccessEnabled', 0],
        web: ['codex.webSearchMode', 'cached'], effort: ['codex.modelReasoningEffort', 'xhigh'],
      }[this.mode];
      if (bad) response.values[bad[0]] = bad[1];
      if (this.mode === 'missing') delete response.values['codex.approvalPolicy'];
    } else {
      assert.equal(channel, 'agentHostManagement');
      assert.equal(command, 'createSessionWithExtensions');
      assert.deepEqual(Object.keys(request.body[0]).sort(), ['config', 'model', 'provider', 'session', 'workingDirectories']);
      assert.deepEqual(request.body[0].model, bridge.MODEL);
      assert.deepEqual(request.body[0].config, bridge.POLICY);
      assert.equal(request.body[0].workingDirectories[0].path, fileURLToPath(workspace));
      // Reproduce pinned model selection: absent model would choose catalog[0].
      assert.equal((request.body[0].model || { id: 'gpt-5.3-codex' }).id, bridge.MODEL.id);
      response = request.body[0].session;
      if (this.mode === 'wrong_session') response = { ...response, path: '/wrong' };
      if (this.mode === 'auth') { code = 202; response = { message: 'Authentication is required', name: 'Error' }; }
    }
    queueMicrotask(() => this.emit('message', bridge.encode([code, id], response)));
    callback?.(); return true;
  }
}

async function run(mode) {
  const child = new FakeChild(mode), records = [], passThrough = [];
  const record = (kind, fields) => records.push({ kind, ...fields });
  const call = bridge.childClient(child, record, 20);
  child.on('message', raw => passThrough.push(raw));
  child.emit('message', bridge.encode([200]));
  const normal = bridge.encode([201, 7], { untouched: true });
  child.emit('message', normal);
  assert.equal(passThrough.at(-1), normal);
  if (mode === 'unknown_channel' || mode === 'unknown_method') {
    await assert.rejects(call(mode === 'unknown_channel' ? 'unknown' : 'agentHostManagement',
      mode === 'unknown_method' ? 'sendMessage' : 'createSessionWithExtensions', []), /management_ipc_call_refused/);
    assert.equal(child.sent.length, 0); return;
  }
  if (mode === 'id_collision') {
    assert.throws(() => child.send(bridge.encode([100, bridge.BASE, 'agentHost', 'anything'], [])), /management_ipc_id_collision/);
    assert.equal(child.sent.length, 0); return;
  }
  if (mode === 'codec') {
    assert.deepEqual(bridge.decode(bridge.encode([100, bridge.BASE, 'agentHost', 'resolveSessionConfig'], [undefined, null, false, 0, '한글', { $mid: 1 }])),
      { header: [100, bridge.BASE, 'agentHost', 'resolveSessionConfig'], body: [undefined, null, false, 0, '한글', { $mid: 1 }] });
    // Independent golden pinned serialize([200]); serialize(undefined).
    assert.equal(bridge.encode([200]), 'BAEGyAEA');
    assert.throws(() => bridge.decode(Buffer.from([4, 1, 6, 200]).toString('base64')), /management_ipc_frame_refused/);
    assert.throws(() => bridge.decode('%%%'), /management_ipc_frame_refused/);
    return;
  }
  let claims = 0;
  const handle = bridge.transaction({ call, workspace, record, claim() { claims++; if (claims !== 1) throw Error('reused'); } });
  const settings = { session, workspace, model: clone(bridge.MODEL), config: clone(bridge.POLICY) };
  if (mode.startsWith('bad_')) {
    const change = mode.slice(4);
    if (change === 'model') settings.model.id = 'gpt-5.3-codex';
    if (change === 'context') settings.model.config.contextSize = 922000;
    if (change === 'effort') settings.model.config.thinkingLevel = 'xhigh';
    if (change === 'permission') settings.config['codex.permissionsPreset'] = 'default';
    if (change === 'network') settings.config['codex.networkAccessEnabled'] = 0;
    if (change === 'workspace') settings.workspace = 'file:///etc';
    if (change === 'session') settings.session = 'ahp-session:/existing';
    if (change === 'field') settings.initialMessage = 'never send';
    await assert.rejects(handle({ id: 1, op: 'configure', params: settings }), /management_init_.*_refused/);
    assert.equal(claims, 0); assert.equal(child.sent.length, 0);
    await assert.rejects(handle({ id: 1, op: 'configure', params: settings }), /management_init_order_refused/);
    return;
  }
  assert.deepEqual(await handle({ id: 1, op: 'configure', params: settings }), { configured: true });
  assert.equal(claims, 1); assert.equal(child.sent.length, 0);
  if (mode === 'no_readback') {
    await assert.rejects(handle({ id: 2, op: 'create', params: {} }), /management_init_order_refused/);
    assert.equal(child.sent.length, 0); return;
  }
  if (['approval', 'sandbox', 'preset', 'network', 'web', 'effort', 'missing', 'lost_reply'].includes(mode)) {
    await assert.rejects(handle({ id: 2, op: 'readback', params: {} }),
      mode === 'lost_reply' ? /management_ipc_timeout/ : /management_init_policy_readback_refused/);
    assert.equal(child.sent.length, 1);
    await assert.rejects(handle({ id: 3, op: 'create', params: {} }), /management_init_order_refused/);
    assert.equal(child.sent.length, 1); assert.equal(claims, 1); return;
  }
  const readback = await handle({ id: 2, op: 'readback', params: {} });
  assert.deepEqual(readback.settings, settings);
  assert.deepEqual(readback.resolved_policy, bridge.POLICY);
  assert.equal(readback.derived_permissions, 'vscode-workspace-read-only');
  assert.equal(readback.admission_allowed, false);
  if (mode === 'readback_tamper') {
    readback.settings.model.id = 'gpt-5.3-codex';
    await assert.rejects(handle({ id: 3, op: 'create', params: {} }), /management_init_readback_refused/);
    assert.equal(child.sent.length, 1); return;
  }
  if (mode === 'wrong_session') {
    await assert.rejects(handle({ id: 3, op: 'create', params: {} }), /management_init_created_identity_refused/);
  } else {
    const created = await handle({ id: 3, op: 'create', params: {} });
    if (mode === 'auth') assert.deepEqual(created, { error: { message: 'Authentication is required', name: 'Error' } });
    else assert.equal(created.result.path, session.slice('ahp-session:'.length));
  }
  assert.equal(child.sent.length, 2);
  await assert.rejects(handle({ id: 4, op: 'create', params: {} }), /management_init_order_refused/);
  assert.equal(child.sent.length, 2); assert.equal(claims, 1);
  assert(!JSON.stringify(child.sent).includes('turn/start'));
  assert.equal(passThrough.length, 2); // init + ordinary response; private replies consumed
}

if (process.argv[2] === 'serve') {
  // Real AF_UNIX + SO_PEERCRED test, but still only a FAKE upstream child.
  const stateRoot = process.argv[3];
  workspace = pathToFileURL(path.join(stateRoot, 'workspace')).href;
  const child = new FakeChild('valid'); child.pid = process.pid;
  const server = bridge.start({ child, stateRoot, directory: path.join(stateRoot, 'wire'),
    bridgeSha256: crypto.createHash('sha256').update(fs.readFileSync(require.resolve('../../ghcp_ahp_management_bridge.cjs'))).digest('hex'),
    record(kind) { if (kind === 'management_bridge_ready') process.stdout.write('ready\n'); } });
  child.emit('message', bridge.encode([200]));
  server.ref();
  process.stdin.resume();
  process.stdin.once('end', () => { child.emit('exit', 0); server.close(); });
} else {
  run(process.argv[2]).then(() => process.stdout.write(JSON.stringify({ ok: true, synthetic: true, turns: 0, external_requests: 0 }) + '\n'),
    error => { console.error(error); process.exitCode = 1; });
}
