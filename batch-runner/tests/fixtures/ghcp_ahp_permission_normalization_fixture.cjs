'use strict';

// Offline pure-function excerpts and fake stdio only. Never import or launch
// Agent Host, Copilot CLI, the native SDK, a model provider or an approval agent.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const { EventEmitter } = require('node:events');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const SOURCE_SHA256 = '82f174deb64825fb97c9a5ef04b4e81bad1e7d0b991ff3dc8435e70f4061dd51';
const PIN = '2c33b50b16c472efe58357d1d2a8a5414bc23fbf';
const digest = value => crypto.createHash('sha256').update(value).digest('hex');

function normalizedCases(input, sourcePath) {
  const raw = fs.readFileSync(sourcePath);
  assert.equal(digest(raw), SOURCE_SHA256, 'permission_fixture_source_drift');
  const fixture = JSON.parse(raw);
  assert.equal(fixture.vscode_commit, PIN);
  assert.equal(fixture.codex_sdk_version, '0.163.0');
  assert.equal(fixture.synthetic, true);
  assert.equal(fixture.execution_allowed, false);
  assert.deepEqual(fixture.files.map(file => file.name), ['common', 'resolution', 'profiles']);
  const fragments = fixture.files.flatMap(file => file.fragments.map(fragment => {
    assert.equal(digest(fragment.text), fragment.sha256, 'permission_fixture_quote_drift');
    return fragment.text;
  }));
  // Only copied type annotations/exports are removed. The function bodies are
  // the byte-bound upstream excerpts, not a second hand-written normalizer.
  const source = fragments.join('\n').replace(/^export /gm, '');
  const javascript = stripTypeScriptTypes(source, { mode: 'transform' });
  const evaluate = `
    if (typeof require !== 'undefined' || typeof process !== 'undefined' || typeof fetch !== 'undefined') {
      throw new Error('permission_fixture_effect_boundary_refused');
    }
    // Supplied by codexAgent.ts:554-557 at this pin, not current web defaults.
    const defaults = { approvalPolicy: 'on-request', sandboxMode: 'workspace-write' };
    JSON.stringify(inputs.map(row => {
      const migrated = migrateCodexPermissionValues(row.config, defaults);
      const resolved = resolveCodexPermissions(migrated, defaults);
      const network = typeof row.config?.['codex.networkAccessEnabled'] === 'boolean'
        ? row.config['codex.networkAccessEnabled'] : false;
      return {
        id: row.id, migrated, resolved,
        migratedAgain: migrateCodexPermissionValues(migrated, defaults),
        permissions: codexPermissionProfile(resolved.sandboxMode, network),
        linuxProfileOverrides: codexPermissionProfileOverrides('/fixture/codex', 'linux'),
        linuxSkillReadOverrides: codexPermissionProfileReadRoots(['/fixture/skills'], 'linux'),
        synthetic: true, execution_allowed: false, native_acceptance_observed: false
      };
    }));
  `;
  return JSON.parse(vm.runInNewContext(javascript + evaluate, { inputs: input }, {
    timeout: 1000, contextCodeGeneration: { strings: false, wasm: false },
  }));
}

function fakeNativeBoundary(row, replyKind) {
  const records = [], writes = [], fakeSpawns = [];
  let claims = 0;
  const child = {
    stdin: { write(value) { writes.push(JSON.parse(value)); return true; }, end() {} },
    stdout: new EventEmitter(),
  };
  const hooks = instrument({
    spawn(command, args) { fakeSpawns.push({ command, args }); return child; },
    fork() { throw new Error('fixture_fork_forbidden'); },
    fetch() { throw new Error('fixture_fetch_forbidden'); },
  }, {
    emit: line => records.push(JSON.parse(line)), nativeBinary: '/fixture/codex',
    nativeSha256: 'a'.repeat(64), modelFree: true, sessionOnly: true, synthetic: true,
    entrypoint: 'vs/platform/agentHost/node/agentHostMain',
    claimThread() { if (claims++) throw new Error('fixture_second_thread_forbidden'); },
  });
  const args = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
    '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
  const stream = hooks.spawn('/fixture/codex', args, {});
  const request = { id: 2, method: 'thread/start', params: {
    model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy',
    approvalPolicy: row.resolved.approvalPolicy, permissions: row.permissions,
    approvalsReviewer: row.resolved.approvalsReviewer,
    config: { web_search: 'disabled', model_context_window: 1000000, model_reasoning_effort: 'max' },
    dynamicTools: [],
  } };
  let refusal = null;
  try {
    stream.stdin.write(JSON.stringify(request) + '\n');
  } catch (error) {
    refusal = error.message;
  }
  if (!refusal && replyKind) {
    // Explicitly synthetic protocol response; not an actual SDK readback.
    const approval = replyKind === 'changed' ? 'on-request' : row.resolved.approvalPolicy;
    const response = { id: 2, result: {
      thread: { id: 'synthetic-thread' }, model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy',
      approvalPolicy: approval, approvalsReviewer: 'user',
      sandbox: { type: 'readOnly', networkAccess: false }, reasoningEffort: 'max',
      activePermissionProfile: { id: row.permissions, extends: 'vscode-workspace' },
    } };
    stream.stdout.emit('data', Buffer.from(JSON.stringify(response) + '\n'));
  }
  assert.equal(fakeSpawns.length, 1);
  assert(writes.length <= 1);
  assert(writes.every(value => value.method === 'thread/start'));
  return { request, writes, records, refusal, claims, synthetic: true,
    vendor_processes_started: 0, model_requests: 0, execution_allowed: false };
}

function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  assert(Array.isArray(input) && input.length <= 200);
  const source = process.argv[2] || path.join(__dirname, 'ghcp_ahp_permission_sources.json');
  const rows = normalizedCases(input, source);
  rows.forEach((row, index) => {
    if (input[index].guard) row.guard = fakeNativeBoundary(row, input[index].reply);
  });
  process.stdout.write(JSON.stringify({ schema: 'ghcp-permission-normalization-offline-v1',
    source_sha256: SOURCE_SHA256, source_commit: PIN, synthetic: true,
    execution_allowed: false, sdk_or_host_executed: false, rows }));
}

try { main(); }
catch {
  // Never echo input data, environment, paths or arbitrary exception messages.
  process.stderr.write('permission_fixture_refused\n');
  process.exitCode = 2;
}
