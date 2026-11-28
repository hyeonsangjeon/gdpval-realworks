'use strict';

// Local, single-use initialization on the already owned ChildProcess IPC.
// VS Code 2c33b50: ipc.cp.ts:29,225; ipc.ts:259-331,1197;
// agentHostMain.ts:267,513; agentHostManagementService.ts:66.
// No AHP model alias, native packet rewrite, credential, or network transport.
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { fileURLToPath, pathToFileURL } = require('node:url');

const MAX = 2 * 1024 * 1024;
const BASE = 0x40000000;
const MODEL = Object.freeze({ id: '@provider=vscode-proxy:gpt-5.6-sol',
  config: Object.freeze({ thinkingLevel: 'max', contextSize: 1000000 }) });
const POLICY = Object.freeze({ 'codex.approvalPolicy': 'untrusted', 'codex.sandboxMode': 'read-only',
  'codex.networkAccessEnabled': false, 'codex.webSearchMode': 'disabled', 'codex.modelReasoningEffort': 'max' });
function fail(reason) { throw Object.assign(new Error(reason), { code: reason }); }
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
  return value;
}
function same(a, b) { return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b)); }
function copy(value) { return JSON.parse(JSON.stringify(value)); }
function uri(scheme, pathname) { return { $mid: 1, scheme, authority: '', path: pathname, query: '', fragment: '' }; }

// The pinned VS Code channel codec, not JSON-RPC. Only its bounded JSON subset
// is emitted. Buffer responses are decoded for framing but never accepted as settings.
function encode(header, body) {
  const parts = [];
  function number(n) {
    n >>>= 0;
    do { const byte = n & 127; n >>>= 7; parts.push(Buffer.from([byte | (n ? 128 : 0)])); } while (n);
  }
  function value(v, depth = 0) {
    if (depth > 32) fail('management_ipc_depth_refused');
    if (v === undefined) parts.push(Buffer.from([0]));
    else if (typeof v === 'string') {
      const b = Buffer.from(v); parts.push(Buffer.from([1])); number(b.length); parts.push(b);
    } else if (Array.isArray(v)) {
      parts.push(Buffer.from([4])); number(v.length); v.forEach(item => value(item, depth + 1));
    } else if (typeof v === 'number' && (v | 0) === v) { parts.push(Buffer.from([6])); number(v); }
    else {
      const b = Buffer.from(JSON.stringify(v)); parts.push(Buffer.from([5])); number(b.length); parts.push(b);
    }
  }
  value(header); value(body);
  const bytes = Buffer.concat(parts);
  if (bytes.length > MAX) fail('management_ipc_size_refused');
  return bytes.toString('base64');
}

function decode(message) {
  if (typeof message !== 'string' || message.length > Math.ceil(MAX / 3) * 4) fail('management_ipc_frame_refused');
  const bytes = Buffer.from(message, 'base64');
  if (bytes.toString('base64') !== message) fail('management_ipc_frame_refused');
  let at = 0, items = 0;
  function take(n) {
    if (!Number.isSafeInteger(n) || n < 0 || at + n > bytes.length) fail('management_ipc_frame_refused');
    const part = bytes.subarray(at, at + n); at += n; return part;
  }
  function number() {
    let result = 0;
    for (let shift = 0; shift < 35; shift += 7) {
      const byte = take(1)[0];
      if (shift === 28 && (byte & 240)) fail('management_ipc_frame_refused');
      result |= (byte & 127) << shift;
      if (!(byte & 128)) return result;
    }
    fail('management_ipc_frame_refused');
  }
  function value(depth = 0) {
    if (++items > 16384 || depth > 32) fail('management_ipc_depth_refused');
    switch (take(1)[0]) {
      case 0: return undefined;
      case 1: return take(number()).toString('utf8');
      case 2: case 3: return take(number());
      case 4: {
        const n = number();
        if (n < 0 || n > 16384) fail('management_ipc_size_refused');
        return Array.from({ length: n }, () => value(depth + 1));
      }
      case 5: return JSON.parse(take(number()).toString('utf8'));
      case 6: return number();
      default: fail('management_ipc_frame_refused');
    }
  }
  const header = value(), body = value();
  if (at !== bytes.length || !Array.isArray(header)) fail('management_ipc_frame_refused');
  return { header, body };
}

function childClient(child, record, timeoutMs = 15000) {
  const send = child.send.bind(child), emit = child.emit;
  let ready = false, next = BASE, closed = false, current;
  function reject(reason) {
    closed = true;
    if (current) { clearTimeout(current.timer); current.reject(Object.assign(new Error(reason), { code: reason })); current = undefined; }
  }
  // Reserve ids disjoint from the pinned parent's counter starting at zero.
  // No normal parent's frame or unrelated response is changed or consumed.
  child.send = function(message, ...rest) {
    if (typeof message === 'string') {
      const { header } = decode(message);
      if (header[1] >= BASE && header[1] < BASE + 16) {
        reject('management_ipc_id_collision'); fail('management_ipc_id_collision');
      }
    }
    return send(message, ...rest);
  };
  child.emit = function(event, ...args) {
    if (event === 'message' && typeof args[0] === 'string') {
      const { header, body } = decode(args[0]);
      if (same(header, [200]) && body === undefined) ready = true;
      else if (header[1] >= BASE && header[1] < BASE + 16) {
        if (!current || header.length !== 2 || header[1] !== current.id || ![201, 202, 203].includes(header[0])) {
          reject('management_ipc_response_identity_refused'); fail('management_ipc_response_identity_refused');
        }
        const pending = current; current = undefined; clearTimeout(pending.timer);
        const response = header[0] === 201 ? { result: body } : { error: body };
        record('management_ipc_response', { channel: pending.channel, command: pending.command, value: response });
        pending.resolve(response);
        return true;
      }
    }
    if (event === 'exit' || event === 'disconnect') reject('management_agent_disconnected');
    return emit.call(this, event, ...args);
  };
  return async function call(channel, command, args) {
    if (closed || !ready || !child.connected || current || next >= BASE + 2 ||
        !(channel === 'agentHost' && command === 'resolveSessionConfig' ||
          channel === 'agentHostManagement' && command === 'createSessionWithExtensions')) fail('management_ipc_call_refused');
    const id = next++;
    record('management_ipc_request', { channel, command, args });
    return new Promise((resolve, rejectPromise) => {
      current = { id, channel, command, resolve, reject: rejectPromise,
        timer: setTimeout(() => reject('management_ipc_timeout'), timeoutMs) };
      try { send(encode([100, id, channel, command], args), error => { if (error) reject('management_ipc_send_failed'); }); }
      catch { reject('management_ipc_send_failed'); }
    });
  };
}

function transaction({ call, workspace, record, claim, admissionProfile }) {
  if (admissionProfile !== undefined && admissionProfile !== 'default_policy_unpatched') fail('management_admission_profile_refused');
  const defaultPolicy = admissionProfile ? require('./ghcp_ahp_default_policy.cjs') : null;
  const policy = defaultPolicy ? {} : POLICY;
  let phase = 'new', staged, receipt;
  const operations = ['configure', 'readback', 'create'];
  let index = 0;
  function check(condition, reason) { if (!condition) fail(reason); }
  function projection(values) {
    return Object.fromEntries(Object.keys(POLICY).map(key => [key, values?.[key] === undefined ? 'not_reported' : values[key]]));
  }
  return async function handle(request) {
    try {
      check(phase !== 'failed' && same(Object.keys(request || {}).sort(), ['id', 'op', 'params']) &&
        request.id === index + 1 && request.op === operations[index], 'management_init_order_refused');
      // Consume before any await. Concurrent input, exceptions and lost replies
      // cannot authorize another initialization or retry the create operation.
      const op = operations[index++];
      if (op === 'configure') {
        check(same(Object.keys(request.params || {}).sort(), ['config', 'model', 'session', 'workspace']), 'management_init_fields_refused');
        const p = request.params;
        check(typeof p.session === 'string' && /^ahp-session:\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(p.session), 'management_init_session_refused');
        check(p.workspace === workspace, 'management_init_workspace_refused');
        check(same(p.model, MODEL) && same(p.config, policy), 'management_init_settings_refused');
        claim();
        staged = copy(p);
        phase = 'configured';
        record('management_configured', { session: p.session, model: p.model, config: p.config });
        return { configured: true };
      }
      check(same(request.params, {}), 'management_init_fields_refused');
      if (op === 'readback') {
        check(phase === 'configured', 'management_init_order_refused'); phase = 'reading';
        const response = await call('agentHost', 'resolveSessionConfig', [{ provider: 'codex',
          workingDirectory: uri('file', fileURLToPath(workspace)), config: copy(staged.config) }]);
        check(phase === 'reading', 'management_init_order_refused');
        if (Object.hasOwn(response, 'error')) { phase = 'failed'; return response; }
        const values = response.result?.values;
        const resolved = defaultPolicy ? defaultPolicy.resolvedPolicy(values) : projection(values);
        record('management_policy_readback', { values: resolved,
          permissions_preset: values?.['codex.permissionsPreset'] ?? 'absent' });
        if (!defaultPolicy) check(same(resolved, POLICY) && !Object.hasOwn(values || {}, 'codex.permissionsPreset'), 'management_init_policy_readback_refused');
        check(same(staged.model, MODEL) && same(staged.config, policy), 'management_init_readback_refused');
        // This is a staged model plus the REAL resolver response, not an
        // applied thread report. The native refusal predicate stays unchanged.
        receipt = { settings: copy(staged), resolved_policy: resolved,
          derived_permissions: defaultPolicy ? 'vscode-workspace' : 'vscode-workspace-read-only',
          evidence: 'staged_model_and_upstream_policy_resolution_not_thread_applied', admission_allowed: false,
          ...(defaultPolicy ? { admission_profile: admissionProfile } : {}) };
        phase = 'verified';
        return receipt;
      }
      check(phase === 'verified' && same(receipt.settings, staged), 'management_init_readback_refused');
      phase = 'consumed';
      const response = await call('agentHostManagement', 'createSessionWithExtensions', [{ provider: 'codex',
        session: uri('ahp-session', staged.session.slice('ahp-session:'.length)),
        workingDirectories: [uri('file', fileURLToPath(workspace))],
        model: copy(staged.model), config: copy(staged.config) }]);
      if (Object.hasOwn(response, 'result')) {
        check(response.result?.scheme === 'ahp-session' && response.result?.path === staged.session.slice('ahp-session:'.length) &&
          !response.result?.authority && !response.result?.query && !response.result?.fragment, 'management_init_created_identity_refused');
      }
      return response;
    } catch (error) {
      phase = 'failed';
      const reason = /^management_[a-z_]+$/.test(error.code || '') ? error.code : 'management_init_internal_refused';
      record('management_init_refused', { reason });
      throw Object.assign(new Error(reason), { code: reason });
    }
  };
}

function start({ child, directory, stateRoot, record, bridgeSha256, admissionProfile }) {
  if (!path.isAbsolute(directory) || directory !== path.join(stateRoot, 'wire') || fs.realpathSync(directory) !== directory ||
      fs.statSync(directory).uid !== process.getuid() || (fs.statSync(directory).mode & 0o777) !== 0o700) fail('management_directory_refused');
  const socketPath = path.join(directory, 'management.sock');
  const claimPath = path.join(directory, 'management-init.claim');
  // Never reuse a previous server, socket or initialization claim.
  if (fs.existsSync(socketPath) || fs.existsSync(claimPath)) fail('management_init_reuse_refused');
  const handle = transaction({ call: childClient(child, record), workspace: pathToFileURL(path.join(stateRoot, 'workspace')).href,
    record, admissionProfile, claim() {
      try { fs.closeSync(fs.openSync(claimPath, 'wx', 0o600)); }
      catch { fail('management_init_reuse_refused'); }
    } });
  let active, connections = 0;
  const server = net.createServer(socket => {
    if (active || ++connections > 3) { socket.destroy(); return; }
    active = socket;
    let buffer = '', consumed = false;
    function finish(reply) {
      if (active === socket) active = undefined;
      socket.end(JSON.stringify(reply) + '\n');
    }
    socket.setEncoding('utf8'); socket.setTimeout(20000, () => socket.destroy());
    socket.on('error', () => {});
    socket.once('close', () => { if (active === socket) active = undefined; });
    socket.on('data', data => {
      buffer += data;
      if (consumed || Buffer.byteLength(buffer) > 16384) { socket.destroy(); return; }
      if (!buffer.endsWith('\n')) return;
      consumed = true;
      let request;
      try { request = JSON.parse(buffer); }
      catch { finish({ ok: false, reason: 'management_init_json_refused' }); return; }
      handle(request).then(result => finish({ id: request.id, ok: true, result }),
        error => finish({ id: request.id, ok: false, reason: error.code }));
    });
  });
  server.on('error', () => { record('management_init_refused', { reason: 'management_socket_failed' }); server.close(); });
  server.listen(socketPath, () => {
    fs.chmodSync(socketPath, 0o600);
    const owner = { schema: 'ghcp-ahp-management-owner-v1', server_pid: process.pid, agent_pid: child.pid,
      uid: process.getuid(), bridge_sha256: bridgeSha256, ...(admissionProfile ? { admission_profile: admissionProfile } : {}) };
    fs.writeFileSync(path.join(directory, 'management-owner.json'), JSON.stringify(owner) + '\n', { flag: 'wx', mode: 0o600 });
    record('management_bridge_ready', owner);
  });
  server.unref();
  child.once('exit', () => server.close());
  return server;
}

module.exports = { encode, decode, childClient, transaction, start, MODEL, POLICY, BASE };
