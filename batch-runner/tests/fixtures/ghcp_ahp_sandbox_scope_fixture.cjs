'use strict';
// Inert stdio + temporary directories only. Never executes a host, SDK or bwrap.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const scenario = process.argv[2];
const state = fs.mkdtempSync(path.join(os.tmpdir(), 'ghcp-scope-fixture-'));
try {
  for (const name of ['tmp', 'home', 'workspace']) fs.mkdirSync(path.join(state, name), { mode: 0o700 });
  const tmp = fs.mkdtempSync(path.join(state, 'tmp', 'vscode-agent-codex-sandbox-'));
  const records = [], writes = [];
  let fetches = 0, spawns = 0, claims = 0;
  const transport = { fork() { throw new Error('forbidden'); },
    fetch() { fetches++; throw new Error('forbidden'); },
    spawn() { spawns++; return { stdin: { write(value) { writes.push(value); return true; } }, stdout: new EventEmitter() }; } };
  const wrapped = instrument(transport, { nativeBinary: '/fixture/codex', nativeSha256: 'a'.repeat(64),
    modelFree: true, sessionOnly: true, synthetic: true, entrypoint: 'vs/platform/agentHost/node/agentHostMain',
    emit: line => records.push(JSON.parse(line)), claimThread() { assert.equal(claims++, 0); },
    forkContract: { schema_version: 'ghcp-ahp-agent-fork-v1', state_root: state } });
  const args = ['app-server', '-c', 'model="gpt-5.6-sol"', '-c', 'model_provider="vscode-proxy"',
    '-c', 'model_reasoning_effort="max"', '-c', 'model_context_window=1000000'];
  const env = { TMPDIR: tmp, TMP: tmp, TEMP: tmp };
  if (scenario === 'unbound_spawn') env.TMPDIR = state;
  const child = wrapped.spawn('/fixture/codex', args, { env });
  const request = { id: 13, method: 'thread/start', params: { model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy',
    approvalPolicy: 'untrusted', permissions: 'vscode-workspace-read-only', config: { web_search: 'disabled' },
    cwd: path.join(state, 'workspace'), runtimeWorkspaceRoots: [path.join(state, 'workspace')] } };
  child.stdin.write(JSON.stringify(request) + '\n');
  const result = { thread: { id: 'fixture-thread' }, model: 'gpt-5.6-sol', modelProvider: 'vscode-proxy',
    reasoningEffort: 'max', approvalPolicy: 'untrusted',
    activePermissionProfile: { id: 'vscode-workspace-read-only', extends: 'vscode-workspace' },
    sandbox: { type: 'workspaceWrite', networkAccess: false, excludeSlashTmp: true,
      excludeTmpdirEnvVar: false, writableRoots: [tmp] } };
  if (scenario === 'normalized') result.sandbox.writableRoots = [tmp + '/./'];
  if (scenario === 'empty') result.sandbox = { type: 'readOnly', networkAccess: false, writableRoots: [] };
  if (scenario === 'empty_legacy') { result.sandbox.writableRoots = []; result.sandbox.excludeTmpdirEnvVar = true; }
  if (scenario === 'two') result.sandbox.writableRoots.push(path.join(state, 'workspace'));
  if (scenario === 'duplicate') result.sandbox.writableRoots.push(tmp);
  if (scenario === 'workspace') result.sandbox.writableRoots = [path.join(state, 'workspace')];
  if (scenario === 'home') result.sandbox.writableRoots = [path.join(state, 'home')];
  if (scenario === 'all_tmp') result.sandbox.writableRoots = ['/tmp'];
  if (scenario === 'state') result.sandbox.writableRoots = [state];
  if (scenario === 'root') result.sandbox.writableRoots = ['/'];
  if (scenario === 'parent') result.sandbox.writableRoots = [path.dirname(tmp)];
  if (scenario === 'child') { fs.mkdirSync(path.join(tmp, 'child')); result.sandbox.writableRoots = [path.join(tmp, 'child')]; }
  if (scenario === 'missing') delete result.sandbox.writableRoots;
  if (scenario === 'null') result.sandbox.writableRoots = null;
  if (scenario === 'not_array') result.sandbox.writableRoots = tmp;
  if (scenario === 'not_string') result.sandbox.writableRoots = [false];
  if (scenario === 'symlink' || scenario === 'symlink_dotdot') {
    const alias = path.join(state, 'tmp', 'alias'); fs.symlinkSync(tmp, alias);
    result.sandbox.writableRoots = [scenario === 'symlink' ? alias : alias + '/../' + path.basename(tmp)];
  }
  if (scenario === 'replaced') { fs.renameSync(tmp, tmp + '-old'); fs.mkdirSync(tmp); }
  if (scenario === 'network') result.sandbox.networkAccess = true;
  if (scenario === 'network_number') result.sandbox.networkAccess = 0;
  if (scenario === 'approval') result.approvalPolicy = 'on-request';
  if (scenario === 'profile') result.activePermissionProfile.id = 'vscode-workspace';
  if (scenario === 'missing_profile') delete result.activePermissionProfile;
  if (scenario === 'implicit_tmp') result.sandbox.writableRoots = [];
  if (scenario === 'implicit_slash_tmp') result.sandbox.excludeSlashTmp = false;
  if (scenario === 'unreported_flags') delete result.sandbox.excludeSlashTmp;
  if (scenario === 'full_access') result.sandbox.type = 'dangerFullAccess';
  if (scenario === 'contradiction') result.sandbox.type = 'readOnly';
  child.stdout.emit('data', Buffer.from(JSON.stringify({ id: 13, result }) + '\n'));
  assert.equal(fetches, 0); assert.equal(spawns, 1); assert.equal(writes.length, 1); assert.equal(claims, 1);
  assert(records.some(row => row.kind === 'native_sandbox_scope'));
  process.stdout.write(JSON.stringify({ state_root: state, records, native_result: result,
    real_processes: 0, model_calls: 0, external_requests: 0 }));
} finally {
  fs.rmSync(state, { recursive: true }); // Exclusively owned mkdtemp fixture.
}
