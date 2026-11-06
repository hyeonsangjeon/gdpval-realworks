'use strict';

// Synthetic parent, genuine vendor bootstrap and byte-observing loader. No AHP requests.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { syncBuiltinESMExports } = require('node:module');
const runtime = require('./ghcp_ahp_patched_runtime.cjs');
const { redactor } = require('./ghcp_ahp_wire_preload.cjs');
const LIMIT = 1024 * 1024;
const DEADLINE_MS = 15000;
const OBSERVATION_MS = 1000;
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const cleanText = (clean, value) => clean.text(value).replace(
  /((?:connectionToken|accessToken|refreshToken|token|authorization|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]');

function boundaryGuards(emit) {
  const deny = operation => function () {
    emit({ kind: 'boundary_refused', operation });
    throw new Error('load_smoke_' + operation + '_refused');
  };
  globalThis.fetch = deny('fetch');
  for (const name of ['node:http', 'node:https']) {
    const module = require(name);
    module.request = deny('http_request'); module.get = deny('http_get');
  }
  const net = require('node:net');
  net.Socket.prototype.connect = deny('socket_connect');
  require('node:tls').connect = deny('tls_connect');
  const listen = net.Server.prototype.listen;
  net.Server.prototype.listen = function (...args) {
    const value = args[0];
    const socketPath = typeof value === 'string' ? value : value?.path;
    if (typeof socketPath !== 'string' || !path.isAbsolute(socketPath) || value?.port !== undefined) {
      return deny('tcp_listen')();
    }
    return listen.apply(this, args); // Local Unix socket only; no incoming TCP listener.
  };
  for (const name of ['spawn', 'spawnSync', 'fork', 'exec', 'execSync', 'execFile', 'execFileSync']) cp[name] = deny('child_process');
  syncBuiltinESMExports();
}

async function child(config) {
  const clean = redactor();
  const emit = value => process.send?.({ ghcp_load_smoke_event: 1, ...clean.clean(value) });
  try {
    const contract = JSON.parse(process.env.GHCP_AHP_PATCHED_RUNTIME_CONTRACT);
    const server = path.dirname(contract.node_path);
    const bootstrap = path.join(server, 'out/bootstrap-fork.js');
    if (config.bootstrap !== bootstrap || sha(fs.readFileSync(bootstrap)) !== config.bootstrap_sha256) {
      throw new Error('load_smoke_bootstrap_identity_refused');
    }
    boundaryGuards(emit);
    runtime.activate({ modelFree: true, sessionOnly: true, entrypoint: contract.entrypoint,
      forkContract: { vscode_commit: contract.upstream_commit, entrypoint: contract.entrypoint,
        files: { node: { path: contract.node_path, sha256: contract.node_sha256 } } } });
    emit({ kind: 'observer_installed', entrypoint: contract.entrypoint, model_free: true, session_only: true,
      synthetic: true, pid: process.pid, ppid: process.ppid, observer: 'existing_patched_runtime_node_load_hook' });
    await import(pathToFileURL(bootstrap).href);
    emit({ kind: 'import_resolved', synthetic: true, pid: process.pid, ppid: process.ppid });
  } catch (error) {
    emit({ kind: 'import_error', message: cleanText(clean, String(error.message)).slice(0, 1000) });
    process.exitCode = 2;
  }
}

async function parent(config) {
  const clean = redactor();
  const contract = JSON.parse(config.environment.GHCP_AHP_PATCHED_RUNTIME_CONTRACT);
  const args = ['--type=agentHost', '--logsPath', config.logs, '--user-data-dir', config.data, '--telemetry-level', 'off'];
  const childEnv = { PATH: '/usr/bin:/bin', LANG: 'C.UTF-8', ...config.environment,
    GHCP_LOAD_SMOKE_CHILD_CONFIG: config.config_path,
    VSCODE_ESM_ENTRYPOINT: contract.entrypoint, VSCODE_PARENT_PID: String(process.pid),
    VSCODE_AGENT_HOST_SOCKET_PATH: config.socket, VSCODE_TELEMETRY_LEVEL: 'off', DO_NOT_TRACK: '1' };
  const worker = cp.fork(__filename, args, { execPath: contract.node_path, execArgv: [],
    env: childEnv, stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
  const events = [], records = [{ kind: 'patched_runtime_child', child_pid: worker.pid,
    parent_pid: process.pid, process: `wire-${process.pid}.jsonl`, synthetic: true,
    runtime_contract_sha256: config.environment.GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256,
    recorded_by: 'synthetic_smoke_parent_actual_fork' }];
  let stdout = '', stderr = '', receivedBytes = 0, imported = false, stopRequested = false;
  let observation, timedOut = false, ipcMessagesReceived = 0;
  const deadline = setTimeout(() => { timedOut = true; worker.kill('SIGKILL'); }, DEADLINE_MS);
  const collect = stream => chunk => {
    receivedBytes += chunk.length;
    if (receivedBytes > LIMIT) { events.push({ kind: 'output_limit_refused' }); worker.kill('SIGKILL'); return; }
    // Buffer only in memory; redact complete streams before persisting, including split tokens.
    const text = chunk.toString('utf8');
    if (stream === 'stdout') stdout += text; else stderr += text;
  };
  worker.stdout.on('data', collect('stdout')); worker.stderr.on('data', collect('stderr'));
  worker.on('message', message => {
    ipcMessagesReceived += 1;
    if (!message || message.ghcp_load_smoke_event !== 1) return; // Never answer or send an IPC/AHP request.
    const row = clean.clean(message);
    events.push(row);
    if (row.kind === 'observer_installed') records.push({ ...row, process: `wire-${worker.pid}.jsonl` });
    if (row.kind === 'import_resolved') {
      imported = true;
      observation = setTimeout(() => { stopRequested = true; worker.kill('SIGTERM'); }, OBSERVATION_MS);
    }
  });
  let launchError = null;
  worker.on('error', error => { launchError = clean.text(error.message); });
  const [exitCode, signal] = await new Promise(resolve => worker.on('close', (code, signal) => resolve([code, signal])));
  clearTimeout(deadline); clearTimeout(observation);
  const authLines = (stdout + '\n' + stderr).split('\n').filter(line => /Authentication is required|AuthRequired|-32007/.test(line));
  const result = { schema: 'ghcp-load-smoke-process-v1', synthetic: true, model_free: true,
    execution_allowed: false, parent_pid: process.pid, child_pid: worker.pid,
    import_resolved: imported, readiness_observed: /Agent host server listening on /.test(stdout),
    authentication_required: authLines.length > 0, authentication_messages: authLines,
    ipc_messages_received: ipcMessagesReceived, ipc_messages_sent: 0, sessions_created: 0, turns_sent: 0,
    stop_requested: stopRequested, observation_ms: OBSERVATION_MS, timed_out: timedOut,
    exit_code: exitCode, signal, launch_error: launchError, events, records,
    stdout: cleanText(clean, stdout), stderr: cleanText(clean, stderr) };
  result.authentication_messages = result.authentication_messages.map(line => cleanText(clean, line));
  fs.writeFileSync(config.process_report, JSON.stringify(result, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
}

async function main() {
  const childPath = process.env.GHCP_LOAD_SMOKE_CHILD_CONFIG;
  const configPath = childPath || process.argv[2];
  if (!configPath || !path.isAbsolute(configPath)) throw new Error('load_smoke_config_refused');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  if (childPath) await child(config); else await parent(config);
}

module.exports = { boundaryGuards, cleanText, DEADLINE_MS, OBSERVATION_MS };
if (require.main === module) main().catch(error => { console.error(String(error.message)); process.exitCode = 2; });
