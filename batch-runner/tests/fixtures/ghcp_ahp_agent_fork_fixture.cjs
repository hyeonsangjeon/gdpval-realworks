'use strict';
// Inert Node module resolution/argument fixtures. fork/spawn/fetch never run.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { instrument } = require('../../ghcp_ahp_wire_preload.cjs');
const input = require('./ghcp_ahp_agent_fork_41941392305.json');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function run(scenario = 'valid') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ahp-fork-fixture-'));
  try {
    const server = path.join(root, 'server'), state = path.join(root, 'state');
    const bind = text => text.replaceAll('${SERVER}', server).replaceAll('${STATE}', state);
    const logs = bind(input.request.args[2]);
    fs.mkdirSync(logs, { recursive: true });
    fs.mkdirSync(path.join(state, 'tmp'));
    fs.mkdirSync(path.join(server, 'out'), { recursive: true });
    fs.writeFileSync(path.join(logs, 'remoteagent.log'), 'inert fixture log');
    const files = {};
    for (const [label, relative] of Object.entries({ node: 'node', module: 'out/bootstrap-fork.js', parent: 'out/server-main.js' })) {
      const location = path.join(server, relative), content = `inert ${label}; never execute`;
      fs.writeFileSync(location, content);
      files[label] = { path: location, sha256: hash(content) };
    }
    const contract = { schema_version: 'ghcp-ahp-agent-fork-v1', vscode_commit: input.provenance.vscode_commit,
      files, module_request: bind(input.request.module_path), state_root: state,
      data_path: path.join(state, 'server-data/data'), logs_root: path.join(state, 'server-data/data/logs'),
      sdk_root: path.join(root, 'codex-sdk'), entrypoint: input.request.entrypoint,
      exec_argv: [], telemetry: 'off' };
    const socket = path.join(state, 'tmp', input.observed_agent_socket_basename);
    const parentArgv = [files.node.path, files.parent.path, '--agent-host-path', socket,
      '--server-data-dir', path.join(state, 'server-data'), '--start-server'];
    let modulePath = contract.module_request, args = input.request.args.map(bind);
    const settings = { execArgv: [], env: { VSCODE_ESM_ENTRYPOINT: contract.entrypoint,
      VSCODE_PIPE_LOGGING: 'true', VSCODE_VERBOSE_LOGGING: 'true',
      VSCODE_PARENT_PID: String(process.pid), VSCODE_AGENT_HOST_SOCKET_PATH: socket,
      VSCODE_AGENT_HOST_CODEX_SDK_ROOT: contract.sdk_root } };
    const records = [], forks = [];
    const forbidden = () => { throw new Error('inert_fixture_crossed_process_or_network_boundary'); };
    let runtimeExecPath = files.node.path;
    if (scenario === 'module_js_alias') modulePath = files.module.path;
    if (scenario === 'module_other') modulePath = files.parent.path;
    if (scenario === 'module_dotdot') modulePath = path.dirname(modulePath) + '/../out/bootstrap-fork';
    if (scenario === 'not_array') args = { ...args };
    if (scenario === 'missing_arg') args.pop();
    if (scenario === 'extra_arg') args.push('--inspect');
    if (scenario === 'reordered') [args[1], args[3]] = [args[3], args[1]];
    if (scenario === 'logs_foreign') args[2] = path.join(root, 'foreign');
    if (scenario === 'data_foreign') args[4] = path.join(root, 'foreign');
    if (scenario === 'telemetry') args[6] = 'all';
    if (scenario === 'logs_ambiguous') fs.mkdirSync(path.join(contract.logs_root, 'second'));
    if (scenario === 'logs_symlink') {
      const target = path.join(root, 'elsewhere');
      fs.renameSync(logs, target); fs.symlinkSync(target, logs);
    }
    if (scenario === 'exec_argv') settings.execArgv.push('--inspect');
    if (scenario === 'exec_path') settings.execPath = files.node.path;
    if (scenario === 'runtime_node') runtimeExecPath = '/foreign/node';
    if (scenario === 'entrypoint') settings.env.VSCODE_ESM_ENTRYPOINT = 'vs/other/main';
    if (scenario === 'node_options') settings.env.NODE_OPTIONS = '--require=foreign';
    if (scenario === 'socket_env') settings.env.VSCODE_AGENT_HOST_SOCKET_PATH += '-other';
    if (scenario === 'socket_foreign') parentArgv[3] = '/foreign/socket';
    if (scenario === 'sdk_root') settings.env.VSCODE_AGENT_HOST_CODEX_SDK_ROOT += '-other';
    if (scenario === 'module_drift') fs.appendFileSync(files.module.path, 'changed');
    if (scenario === 'node_drift') fs.appendFileSync(files.node.path, 'changed');
    if (scenario === 'parent_drift') fs.appendFileSync(files.parent.path, 'changed');
    if (scenario === 'module_shadow') fs.writeFileSync(contract.module_request, 'unapproved extensionless file');
    if (scenario === 'parent_path') parentArgv[1] = '/foreign/main.js';
    if (scenario === 'module_symlink') {
      fs.renameSync(files.module.path, path.join(root, 'foreign.js'));
      fs.symlinkSync(path.join(root, 'foreign.js'), files.module.path);
    }
    const unseeded = 'UNSEEDED_PRIVATE_FIXTURE_64832';
    if (scenario === 'credential_args') args.push('--password', unseeded, '--access-token=' + unseeded, '--auth', unseeded);
    const hooks = instrument({ spawn: forbidden, fetch: forbidden,
      fork(...values) { forks.push(values); return 'inert-child'; } }, {
      emit: line => records.push(JSON.parse(line)), synthetic: true, modelFree: true,
      nativeBinary: '/inert/native', nativeSha256: 'a'.repeat(64),
      observerPath: '/fixture/observer.cjs', observerSha256: 'b'.repeat(64),
      forkContract: contract,
      runtimeExecPath, parentArgv, parentPid: process.pid,
      entrypoint: 'server-main.js',
    });
    if (scenario === 'valid') {
      assert.equal(hooks.fork(modulePath, args, settings), 'inert-child');
      assert.equal(forks.length, 1);
      assert.equal(forks[0][0], modulePath);
      assert.deepEqual(forks[0][1], args);
      assert.deepEqual(forks[0][2].execArgv, ['--require', '/fixture/observer.cjs']);
      assert.deepEqual(settings.execArgv, []);
      assert.equal(forks[0][2].env.NODE_OPTIONS, undefined);
    } else {
      assert.throws(() => hooks.fork(modulePath, args, settings), /wire_agent_fork_refused/);
      assert.equal(forks.length, 0);
    }
    assert(!JSON.stringify(records).includes(unseeded));
    return records;
  } finally {
    fs.rmSync(root, { recursive: true }); // Only this mkdtemp-owned inert fixture.
  }
}

module.exports = { run };
if (require.main === module) process.stdout.write(JSON.stringify(run(process.argv[2])));
