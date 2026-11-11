'use strict';
// Only inert files and fake stdio. Never execute a vendor host/SDK or a tool.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');
const { pathToFileURL } = require('node:url');
const modules = require('node:module');
const policy = require('../../ghcp_ahp_default_policy.cjs');
const bridge = require('../../ghcp_ahp_management_bridge.cjs');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const mode = process.argv[2], root = process.argv[3];
const sha = data => crypto.createHash('sha256').update(data).digest('hex');

async function main() {
  if (mode.startsWith('management')) {
    const calls = [];
    const defaults = { 'codex.permissionsPreset': 'default', mode: 'interactive' };
    const handle = bridge.transaction({ admissionProfile: policy.PROFILE, workspace: 'file:///tmp/fixture/workspace',
      record() {}, claim() {}, async call(channel, command, args) {
        calls.push({ channel, command, args });
        if (command === 'resolveSessionConfig') return { result: { values: defaults } };
        return { result: { scheme: 'ahp-session', path: '/12345678-1234-4234-8234-123456789abc' } };
      } });
    const settings = { session: 'ahp-session:/12345678-1234-4234-8234-123456789abc',
      workspace: 'file:///tmp/fixture/workspace', model: bridge.MODEL, config: {} };
    if (mode === 'management_read_only') settings.config = bridge.POLICY;
    if (mode === 'management_read_only') {
      await assert.rejects(handle({ id: 1, op: 'configure', params: settings }), /management_init_settings_refused/);
      assert.equal(calls.length, 0); return;
    }
    await handle({ id: 1, op: 'configure', params: settings });
    if (mode === 'management_network') defaults['codex.networkAccessEnabled'] = true;
    if (mode === 'management_network') {
      await assert.rejects(handle({ id: 2, op: 'readback', params: {} }), /management_default_policy_readback_refused/);
      await assert.rejects(handle({ id: 3, op: 'create', params: {} }), /management_init_order_refused/);
      assert.equal(calls.length, 1); return;
    }
    const report = await handle({ id: 2, op: 'readback', params: {} });
    assert.equal(report.admission_profile, policy.PROFILE);
    assert.equal(report.resolved_policy['codex.approvalPolicy'], 'not_reported');
    assert.equal(report.derived_permissions, 'vscode-workspace');
    assert.equal(report.admission_allowed, false);
    await handle({ id: 3, op: 'create', params: {} });
    assert.equal(calls.length, 2);
    assert.deepEqual(calls[1].args[0].config, {});
    assert.equal(calls[1].args[0].model.id, '@provider=vscode-proxy:gpt-5.6-sol');
    return;
  }
  const workspace = path.join(root, 'workspace'), temporary = path.join(root, 'tmp/job-temp');
  fs.mkdirSync(workspace, { recursive: true }); fs.mkdirSync(temporary, { recursive: true });
  const node = path.join(root, 'server/node'), entry = path.join(root, 'server', policy.RELATIVE);
  fs.mkdirSync(path.dirname(entry), { recursive: true });
  fs.writeFileSync(node, 'inert fixture node identity, never executed\n');
  fs.writeFileSync(entry, 'export const fixture = true;\n');
  const contract = { schema: 'ghcp-default-unpatched-load-contract-v1', admission_profile: policy.PROFILE,
    vscode_commit: policy.PIN, server_archive_sha256: policy.ARCHIVE, state_root: root,
    node: { path: node, sha256: sha(fs.readFileSync(node)) }, entry: { path: entry, sha256: sha(fs.readFileSync(entry)) },
    loader_sha256: sha(fs.readFileSync(require.resolve('../../ghcp_ahp_default_policy.cjs'))), challenge: 'a'.repeat(32),
    patched_ghcp: false, patches_applied: [], execution_allowed: false, synthetic: true };
  // This is explicitly counterfactual process metadata for an inert loader
  // unit test. The live consumer rejects synthetic=true before authentication.
  process.execPath = node;
  const records = [], writes = [];
  let claims = 0;
  const options = { admissionProfile: policy.PROFILE, defaultPolicyContract: contract,
    defaultPolicyContractSha256: sha(JSON.stringify(contract)),
    emit: text => records.push(JSON.parse(text)), modelFree: true, sessionOnly: true, synthetic: true,
    entrypoint: policy.ENTRYPOINT, nativeBinary: '/fixture/codex', nativeSha256: 'b'.repeat(64),
    forkContract: { schema_version: 'ghcp-ahp-agent-fork-v1', vscode_commit: policy.PIN, entrypoint: policy.ENTRYPOINT,
      state_root: root, files: { node: contract.node } },
    claimThread() { if (claims++) throw Error('repeated'); } };
  const transports = { fork() { throw Error('not called'); }, fetch() { throw Error('egress forbidden'); },
    spawn() { return { stdin: { write(value) { writes.push(value); return true; }, end(value) { if (value) writes.push(value); } },
      stdout: new EventEmitter() }; } };
  if (mode === 'old_profile') delete options.admissionProfile;
  if (mode === 'mixed') options.patchedRuntime = {};
  if (mode === 'tampered') fs.appendFileSync(entry, ' ');
  if (mode === 'mixed' || mode === 'tampered') {
    assert.throws(() => instrument(transports, options), /default_policy_/); return;
  }
  if (mode === 'loaded_mismatch') modules.registerHooks({ load(url, context, next) {
    const loaded = next(url, context);
    return url === pathToFileURL(entry).href ? { ...loaded, source: loaded.source + '\nexport const altered = true;' } : loaded;
  } });
  const hooks = instrument(transports, options);
  if (mode === 'after_binding') fs.appendFileSync(entry, ' ');
  if (mode === 'after_binding' || mode === 'loaded_mismatch') {
    await assert.rejects(import(pathToFileURL(entry).href), /default_policy_(?:before_load|loaded_source)_mismatch/); return;
  }
  if (mode !== 'old_profile') {
    await import(pathToFileURL(entry).href);
    assert.equal(records.filter(row => row.kind === 'default_policy_loaded').length, 1);
  }
  const args = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
    '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
  const child = hooks.spawn('/fixture/codex', args, { env: { TMPDIR: temporary, TMP: temporary, TEMP: temporary } });
  const request = { id: 2, method: 'thread/start', params: { model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy',
    approvalPolicy: 'on-request', permissions: 'vscode-workspace', approvalsReviewer: 'user',
    cwd: workspace, runtimeWorkspaceRoots: [workspace], config: { web_search: 'disabled', model_context_window: 1000000 } } };
  const encode = value => JSON.stringify(value) + '\n';
  if (mode === 'read_only') { request.params.approvalPolicy = 'untrusted'; request.params.permissions = 'vscode-workspace-read-only'; }
  if (mode === 'unsafe_network') request.params.permissions = 'vscode-workspace-network';
  if (mode === 'sandbox_off') { delete request.params.permissions; request.params.sandbox = 'danger-full-access'; }
  if (mode === 'wrong_model') request.params.model = 'gpt-5.3-codex';
  if (mode === 'wrong_effort') request.params.config.model_reasoning_effort = 'xhigh';
  if (['read_only', 'unsafe_network', 'sandbox_off', 'wrong_model', 'wrong_effort', 'old_profile'].includes(mode)) {
    assert.throws(() => child.stdin.write(encode(request)), mode === 'old_profile' ? /session_policy_thread_contract_refused/ : /default_policy_thread_contract_refused/);
    assert.equal(writes.length, 0); assert.equal(claims, 0); return;
  }
  if (mode.startsWith('rpc_')) {
    const method = { rpc_turn: 'turn/start', rpc_hook: 'hooks/run', rpc_exec: 'command/exec', rpc_resume: 'thread/resume', rpc_write: 'config/write' }[mode];
    assert.throws(() => child.stdin.write(encode({ id: 11, method, params: {} })), /wire_model_free_rpc_refused/);
    assert.equal(writes.length, 0); return;
  }
  child.stdin.write(encode(request));
  assert.equal(writes.length, 1); assert.equal(writes[0], encode(request));
  const result = { thread: { id: 'fixture-thread' }, model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy', reasoningEffort: 'max',
    approvalPolicy: 'on-request', activePermissionProfile: { id: 'vscode-workspace' },
    sandbox: { type: 'workspaceWrite', networkAccess: false, writableRoots: [workspace, temporary], excludeSlashTmp: true, excludeTmpdirEnvVar: true } };
  if (mode === 'reply_network') result.sandbox.networkAccess = true;
  if (mode === 'reply_global_tmp') result.sandbox.writableRoots = ['/tmp'];
  if (mode === 'reply_duplicate') result.sandbox.writableRoots = [workspace, workspace];
  if (mode === 'reply_missing') delete result.sandbox.writableRoots;
  if (mode === 'reply_symlink') {
    const link = path.join(root, 'linked-workspace'); fs.symlinkSync(workspace, link);
    result.sandbox.writableRoots = [link, temporary];
  }
  child.stdout.emit('data', Buffer.from(encode({ id: 2, result })));
  const scope = records.find(row => row.kind === 'default_policy_sandbox_scope');
  assert.equal(scope.admission_profile, policy.PROFILE);
  assert.equal(scope.status, mode.startsWith('reply_') ? 'refused' : 'measured');
  if (!mode.startsWith('reply_')) {
    assert.equal(scope.reported_writable_roots[0], '[REDACTED]');
    assert.equal(scope.workspace_identity.path_sha256, sha(workspace));
    assert.equal(scope.reported_writable_roots[1], temporary);
  }
  assert.throws(() => child.stdin.write(encode(request)), /session_policy_thread_limit/);
  assert.equal(writes.length, 1);
  for (const endpoint of ['https://api.githubcopilot.com/responses', 'https://api.githubcopilot.com/chat/completions'])
    await assert.rejects(hooks.fetch(endpoint, { method: 'POST' }), /session_policy_http_refused/);
}

main().then(() => process.stdout.write(JSON.stringify({ ok: true, synthetic: true, model_calls: 0, native_processes: 0 }) + '\n'),
  error => { console.error(error); process.exitCode = 1; });
