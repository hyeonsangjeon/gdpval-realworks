'use strict';

// Diagnostic tee, not a provider, proxy, authentication source or admission gate.
// Node's pinned Agent Host uses child_process.spawn and globalThis.fetch.
// See ghcp-ahp-wire-capture.md for the exact upstream source contracts.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { StringDecoder } = require('node:string_decoder');
const { syncBuiltinESMExports } = require('node:module');

const LIMIT = 2 * 1024 * 1024;
const TOTAL = 16 * 1024 * 1024;
const READ_ONLY_RPC = new Set(['initialize', 'initialized', 'model/list', 'config/read',
  'configRequirements/read', 'account/read', 'account/rateLimits/read', 'mcpServerStatus/list',
  'skills/list', 'plugin/list', 'permissionProfile/list', 'thread/list']);
const PRIVATE = /^(?:auth|authentication|authorization|cookie|setcookie|account|accounts|accountid|accountname|user|userid|username|email|tenant|tenantid|organization|orgid|identity|login|password|secret|credential|credentials|token|accesstoken|refreshtoken|idtoken|apikey|cwd|workingdirectory|workingdirectories|homedir)$/;
const fail = code => { throw new Error(code); };
function parseJson(text) {
  try { return JSON.parse(text); } catch { fail('wire_json_invalid'); }
}

function redactor(seeds = []) {
  const known = new Set();
  function remember(value) {
    if (typeof value !== 'string' || !value || value === '[REDACTED]') return;
    if (value.length > 16384 || known.size > 4096) fail('wire_redaction_limit');
    for (const text of [value, JSON.stringify(value).slice(1, -1), encodeURIComponent(value),
      Buffer.from(value).toString('base64'), Buffer.from(value).toString('base64url')]) known.add(text);
    if (/^Bearer /i.test(value)) remember(value.slice(7));
  }
  seeds.forEach(remember);
  function privateKey(key) {
    const name = key.toLowerCase().replace(/[^a-z]/g, '');
    return PRIVATE.test(name) || /(?:token|apikey|password|secret|accountid|userid|username|email|tenantid)$/.test(name);
  }
  function learn(value, secret = false) {
    if (Array.isArray(value)) value.forEach(item => learn(item, secret));
    else if (value && typeof value === 'object') {
      for (const [key, item] of Object.entries(value)) learn(item, secret || privateKey(key));
    } else if (secret) remember(String(value));
  }
  function text(value) {
    for (const secret of [...known].sort((a, b) => b.length - a.length)) value = value.split(secret).join('[REDACTED]');
    return value.replace(/\b(?:github_pat_|gh[opusr]_|sk-)[A-Za-z0-9_-]{8,}/g, '[REDACTED]')
      .replace(/\bBearer\s+[^\s"<>]+/gi, 'Bearer [REDACTED]')
      .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[REDACTED]')
      .replace(/("(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*")/g,
        (whole, key) => privateKey(parseJson(key)) ? `${key}:"[REDACTED]"` : whole);
  }
  function clean(value) {
    learn(value);
    function visit(item) {
      if (typeof item === 'string') return text(item);
      if (Array.isArray(item)) return item.map(visit);
      if (item && typeof item === 'object') return Object.fromEntries(Object.entries(item).map(
        ([key, data]) => [text(key), privateKey(key) ? '[REDACTED]' : visit(data)]));
      return item;
    }
    return visit(value);
  }
  return { clean, text, learn };
}

function frames(onFrame, delimiter) {
  const decoder = new StringDecoder('utf8');
  let pending = '';
  function drain() {
    let match;
    while ((match = delimiter.exec(pending))) {
      const end = match.index + match[0].length;
      onFrame(pending.slice(0, end));
      pending = pending.slice(end);
    }
    if (Buffer.byteLength(pending) > LIMIT) fail('wire_frame_limit');
  }
  return {
    feed(chunk) { pending += typeof chunk === 'string' ? chunk : decoder.write(chunk); drain(); },
    end() {
      pending += decoder.end(); drain();
      if (pending.trim()) fail('wire_truncated_frame');
    },
  };
}

function safeArguments(args) {
  if (!Array.isArray(args)) return { shape: typeof args };
  let privateNext = false;
  return args.map(arg => {
    if (privateNext) { privateNext = false; return '[REDACTED]'; }
    if (typeof arg !== 'string') return { shape: typeof arg };
    const [flag] = arg.split('=', 1);
    if (flag.startsWith('--') && /token|secret|password|credential|api[-_]?key|auth|cookie/i.test(flag)) {
      if (arg.includes('=')) return flag + '=[REDACTED]';
      privateNext = true;
    }
    return arg;
  });
}

function checkAgentFork(modulePath, args, settings, options) {
  const contract = options.forkContract;
  const mismatches = [], expected = {};
  const same = (left, right) => Array.isArray(left) && Array.isArray(right) &&
    left.length === right.length && left.every((value, index) => value === right[index]);
  function check(condition, name) { if (!condition) mismatches.push(name); }
  try {
    if (contract?.schema_version !== 'ghcp-ahp-agent-fork-v1') throw new Error('contract');
    Object.assign(expected, { module_path: contract.module_request, executable: contract.files.node.path,
      entrypoint: contract.entrypoint, exec_argv: contract.exec_argv });
    check(modulePath === contract.module_request, 'module_request');
    check(options.runtimeExecPath === contract.files.node.path, 'runtime_executable');
    check(options.parentArgv?.[1] === contract.files.parent.path, 'parent_script');
    check(same(Object.keys(settings || {}).sort(), ['env', 'execArgv']), 'fork_option_keys');
    check(same(settings?.execArgv, contract.exec_argv), 'exec_argv');
    check(Boolean(options.observerPath) && path.isAbsolute(options.observerPath), 'observer_path');
    for (const [label, file] of Object.entries(contract.files)) {
      check(fs.lstatSync(file.path).isFile() && fs.realpathSync(file.path) === file.path &&
        crypto.createHash('sha256').update(fs.readFileSync(file.path)).digest('hex') === file.sha256, `${label}_identity`);
    }
    check(typeof modulePath === 'string' && require.resolve(modulePath) === contract.files.module.path, 'module_resolution');
    check(fs.realpathSync(contract.logs_root) === contract.logs_root, 'logs_root');
    // Exactly one directory created by this invocation's pinned server. No glob,
    // basename wildcard, caller-selected directory, or timestamp guess.
    const directories = fs.readdirSync(contract.logs_root, { withFileTypes: true });
    if (directories.length !== 1 || !directories[0].isDirectory()) throw new Error('logs');
    const logs = path.join(contract.logs_root, directories[0].name);
    check(fs.realpathSync(logs) === logs && fs.lstatSync(path.join(logs, 'remoteagent.log')).isFile(), 'logs_identity');
    expected.args = ['--type=agentHost', '--logsPath', logs,
      '--user-data-dir', contract.data_path, '--telemetry-level', contract.telemetry];
    check(same(args, expected.args), 'argv_exact');
    const parentArgs = options.parentArgv || [];
    const indices = parentArgs.flatMap((value, index) => value === '--agent-host-path' ? [index] : []);
    const socket = indices.length === 1 ? parentArgs[indices[0] + 1] : undefined;
    expected.socket_path = socket;
    check(typeof socket === 'string' && path.isAbsolute(socket) && path.normalize(socket) === socket &&
      path.dirname(socket) === path.join(contract.state_root, 'tmp') &&
      fs.realpathSync(path.dirname(socket)) === path.dirname(socket), 'parent_socket');
    const env = settings?.env || {};
    check(env.VSCODE_ESM_ENTRYPOINT === contract.entrypoint, 'entrypoint');
    check(env.VSCODE_PIPE_LOGGING === 'true' && env.VSCODE_VERBOSE_LOGGING === 'true', 'ipc_logging');
    check(env.VSCODE_PARENT_PID === String(options.parentPid), 'parent_pid');
    check(env.VSCODE_AGENT_HOST_SOCKET_PATH === socket, 'socket_env');
    check(env.VSCODE_AGENT_HOST_CODEX_SDK_ROOT === contract.sdk_root, 'sdk_root');
    check(!Object.hasOwn(env, 'NODE_OPTIONS'), 'inherited_node_options');
  } catch {
    mismatches.push('contract_resolution');
  }
  return { expected, mismatches };
}

function diagnosticScalar(value) {
  const type = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
  // Never truncate before redaction: a token prefix could otherwise survive.
  // No nested prompt, path, tool body or MCP URL is included in this projection.
  const safe = type === 'undefined' ? 'not_reported' : value === null ? null :
    type === 'string' ? (value.length > 256 ? '[VALUE_TOO_LONG]' : value) :
    ['boolean', 'number'].includes(type) ? value : '[NON_SCALAR]';
  return { type, value: safe };
}

function threadContractDiagnostic(message, modelFree, readOnly) {
  // Diagnostics only, called AFTER the unchanged refusal predicate fires.
  // These comparisons neither authorize nor rewrite a native request.
  const p = message.params, config = p?.config, rejections = [];
  const check = (field, accepted, expected, actual) => {
    if (!accepted) rejections.push({ field, expected, actual });
  };
  check('modelFree', modelFree, true, diagnosticScalar(modelFree));
  check('params', Boolean(p), { truthy: true }, diagnosticScalar(p));
  check('params.model', p?.model === 'gpt-5.6-sol', 'gpt-5.6-sol', diagnosticScalar(p?.model));
  check('params.modelProvider', p?.modelProvider === 'vscode-proxy', 'vscode-proxy', diagnosticScalar(p?.modelProvider));
  check('params.approvalPolicy', p?.approvalPolicy === 'untrusted', 'untrusted', diagnosticScalar(p?.approvalPolicy));
  check('params.sandbox/permissions', readOnly, { one_of: [
    { sandbox: 'read-only', permissions: 'absent' },
    { sandbox: 'absent', permissions: 'vscode-workspace-read-only' },
  ] }, { sandbox: diagnosticScalar(p?.sandbox), permissions: diagnosticScalar(p?.permissions) });
  check('params.config', Boolean(config), { truthy: true }, diagnosticScalar(config));
  check('params.config.web_search', config?.web_search === 'disabled', 'disabled', diagnosticScalar(config?.web_search));
  check('params.allowProviderModelFallback', p?.allowProviderModelFallback === undefined || p.allowProviderModelFallback === false,
    { absent_or: false }, diagnosticScalar(p?.allowProviderModelFallback));
  check('params.config.model_context_window', config?.model_context_window === undefined || config.model_context_window === 1000000,
    { absent_or: 1000000 }, diagnosticScalar(config?.model_context_window));
  check('params.config.model_reasoning_effort', config?.model_reasoning_effort === undefined || config.model_reasoning_effort === 'max',
    { absent_or: 'max' }, diagnosticScalar(config?.model_reasoning_effort));
  const mcpEntries = Object.keys(config?.mcp_servers || {}).length;
  check('params.config.mcp_servers', mcpEntries === 0, { entry_count: 0 },
    { type: diagnosticScalar(config?.mcp_servers).type, entry_count: mcpEntries });
  check('id.type', ['string', 'number'].includes(typeof message.id), ['string', 'number'], diagnosticScalar(message.id).type);
  check('result', !Object.hasOwn(message, 'result'), { present: false }, { present: Object.hasOwn(message, 'result') });
  check('error', !Object.hasOwn(message, 'error'), { present: false }, { present: Object.hasOwn(message, 'error') });
  return { rejected_fields: rejections.map(row => row.field), rejections };
}

function instrument({ spawn, fetch, fork }, options) {
  const metadata = require('./ghcp_ahp_metadata_client.cjs');
  const { emit, nativeBinary, nativeSha256, modelFree, synthetic = false, seeds = [] } = options;
  const sessionOnly = options.sessionOnly === true;
  if (sessionOnly && modelFree !== true) fail('session_policy_mode_refused');
  if (options.metadataRequest && (!sessionOnly || modelFree !== true)) fail('metadata_mode_refused');
  const mask = redactor(seeds);
  let sequence = 0, bytes = 0, ipcNumber = 0, httpNumber = 0;
  let threadRequestId, threadStream, ownedThread;
  function record(kind, fields = {}) {
    const safe = mask.clean({ sequence: ++sequence, kind, synthetic, ...fields });
    const line = JSON.stringify(safe) + '\n';
    bytes += Buffer.byteLength(line);
    if (bytes > TOTAL || sequence > 8192) fail('wire_capture_limit');
    emit(line);
  }
  function raw(kind, fields, value, text) {
    mask.learn(value);
    record(kind, { ...fields, value, wire_text_redacted: mask.text(text) });
  }
  function blocked(boundary, reason, details = {}) {
    record('blocked', { boundary, reason, ...details });
    fail(reason);
  }
  function requestAllowed(message, stream) {
    if (sessionOnly && message.method === 'thread/start') {
      const p = message.params, config = p?.config;
      const readOnly = p?.sandbox === 'read-only' && p?.permissions === undefined ||
        p?.permissions === 'vscode-workspace-read-only' && p?.sandbox === undefined;
      // The named permission is the pinned harness's own raw-axis translation,
      // NOT a client-selected codex.permissionsPreset or proof of its effect.
      if (!modelFree || !p || p.model !== 'gpt-5.6-sol' || p.modelProvider !== 'vscode-proxy' ||
          p.approvalPolicy !== 'untrusted' || !readOnly || !config || config.web_search !== 'disabled' ||
          p.allowProviderModelFallback !== undefined && p.allowProviderModelFallback !== false ||
          config.model_context_window !== undefined && config.model_context_window !== 1000000 ||
          config.model_reasoning_effort !== undefined && config.model_reasoning_effort !== 'max' ||
          Object.keys(config.mcp_servers || {}).length !== 0 || !['string', 'number'].includes(typeof message.id) ||
          Object.hasOwn(message, 'result') || Object.hasOwn(message, 'error')) {
        blocked('native_ipc', 'session_policy_thread_contract_refused', threadContractDiagnostic(message, modelFree, readOnly));
      }
      if (threadRequestId !== undefined || !options.claimThread) blocked('native_ipc', 'session_policy_thread_limit');
      try { options.claimThread(); } catch { blocked('native_ipc', 'session_policy_thread_limit'); }
      threadRequestId = message.id; threadStream = stream;
      return;
    }
    if (sessionOnly && ['thread/unsubscribe', 'thread/archive'].includes(message.method)) {
      if (!ownedThread || stream !== threadStream || message.params?.threadId !== ownedThread ||
          Object.keys(message.params).length !== 1 || Object.hasOwn(message, 'result') || Object.hasOwn(message, 'error')) {
        blocked('native_ipc', 'session_policy_foreign_cleanup_refused');
      }
      return;
    }
    if (modelFree && (!READ_ONLY_RPC.has(message.method) || Object.hasOwn(message, 'result') || Object.hasOwn(message, 'error'))) {
      blocked('native_ipc', 'wire_model_free_rpc_refused');
    }
  }
  function wrappedSpawn(command, args, settings) {
    if (path.resolve(String(command)) !== nativeBinary || !Array.isArray(args) || args[0] !== 'app-server') {
      return spawn(command, args, settings);
    }
    if (options.verifyBinary) options.verifyBinary(nativeBinary, nativeSha256);
    if (sessionOnly) {
      const overrides = args.flatMap((arg, index) => arg === '-c' ? [args[index + 1]] : []);
      for (const required of ['model="gpt-5.6-sol"', 'model_provider="vscode-proxy"',
        'model_reasoning_effort="max"', 'model_context_window=1000000']) {
        const key = required.split('=')[0];
        const found = overrides.filter(value => typeof value === 'string' && value.split('=')[0].trim() === key);
        if (found.length !== 1 || found[0] !== required) blocked('native_spawn', 'session_policy_launch_config_refused');
      }
    }
    const stream = `ipc-${++ipcNumber}`;
    // Do not leak diagnostic bootstrap data or recursively preload tool children.
    const env = { ...(settings?.env || process.env) };
    mask.learn({ apiKey: env.OPENAI_API_KEY });
    for (const key of Object.keys(env)) if (key.startsWith('GHCP_AHP_WIRE_') || key === 'NODE_OPTIONS') delete env[key];
    const child = spawn(command, args, { ...settings, env });
    record('native_started', { stream, native_binary_sha256: nativeSha256, session_only: sessionOnly });
    const outgoing = frames(text => {
      const value = parseJson(text);
      requestAllowed(value, stream); // Before the original write, including batched lines.
      raw('ipc_request', { stream, delivery: 'attempted' }, value, text);
    }, /\r?\n/);
    const incoming = frames(text => {
      const value = parseJson(text);
      if (sessionOnly && /^(?:turn\/|item\/)/.test(value.method || '')) blocked('native_event', 'session_policy_turn_or_tool_refused');
      if (sessionOnly && value.id === threadRequestId && stream === threadStream && typeof value.result?.thread?.id === 'string') {
        ownedThread = value.result.thread.id;
      }
      raw('ipc_response', { stream }, value, text);
    }, /\r?\n/);
    const originalWrite = child.stdin.write;
    function inspectOutgoing(chunk) {
      // The pinned client writes complete newline-delimited messages. Never
      // forward a partial free-mode packet: a child could parse it on EOF.
      if (modelFree && !Buffer.from(chunk).toString('utf8').endsWith('\n')) blocked('native_ipc', 'wire_model_free_partial_rpc_refused');
      outgoing.feed(chunk);
      if (modelFree) outgoing.end();
    }
    child.stdin.write = function (chunk, ...rest) {
      inspectOutgoing(typeof chunk === 'string' ? Buffer.from(chunk, typeof rest[0] === 'string' ? rest[0] : 'utf8') : chunk);
      return originalWrite.call(this, chunk, ...rest);
    };
    if (typeof child.stdin.end === 'function') {
      const originalEnd = child.stdin.end;
      child.stdin.end = function (chunk, ...rest) {
        if (typeof chunk === 'string' || Buffer.isBuffer(chunk)) inspectOutgoing(Buffer.from(chunk));
        outgoing.end();
        return originalEnd.call(this, chunk, ...rest);
      };
    }
    const originalEmit = child.stdout.emit;
    child.stdout.emit = function (event, ...rest) {
      // Observe existing consumption; never add a data listener that forces flow.
      if (event === 'data') incoming.feed(rest[0]);
      if (event === 'end') incoming.end();
      return originalEmit.call(this, event, ...rest);
    };
    return child;
  }
  function wrappedFork(modulePath, args, settings) {
    const checked = checkAgentFork(modulePath, args, settings, options);
    record('agent_fork_attempt', { module_path: typeof modulePath === 'string' ? modulePath : null,
      executable: settings?.execPath || options.runtimeExecPath, args: safeArguments(args),
      exec_argv: safeArguments(settings?.execArgv), entrypoint: settings?.env?.VSCODE_ESM_ENTRYPOINT,
      ...checked });
    if (checked.mismatches.length) {
      record('blocked', { boundary: 'agent_host_fork', reason: 'wire_agent_fork_refused', mismatches: checked.mismatches });
      fail('wire_agent_fork_refused');
    }
    // VS Code intentionally strips NODE_OPTIONS from forks. Add only this
    // hash-bound observer as an explicit execArgv, never restore arbitrary options.
    const env = { ...settings.env, GHCP_AHP_WIRE_SEEDS: JSON.stringify(seeds) };
    const execArgv = [...(settings.execArgv || []), '--require', options.observerPath];
    record('agent_fork_instrumented');
    return fork(modulePath, args, { ...settings, env, execArgv });
  }
  async function wrappedFetch(url, init) {
    if (sessionOnly && options.metadataRequest) {
      const location = metadata.coordinates(url, init);
      let message;
      try { message = metadata.request(url, init); }
      catch { blocked('metadata_http', 'metadata_request_refused', { ...location, forwarded: false }); }
      record('metadata_request', location);
      let response;
      try { response = await options.metadataRequest(message); }
      catch { blocked('metadata_http', 'metadata_broker_refused', { ...location, forwarded: false }); }
      record('metadata_response', { ...location, status: response.status, external_request: response.external_request });
      if (response.status !== 200) blocked('metadata_http', 'metadata_status_refused', location);
      return new Response(response.body, { status: response.status, headers: response.headers });
    }
    // This mode has no HTTP allowance, including model catalogs/auth refresh.
    // Stop before parsing/calling fetch, not merely after a failed network call.
    if (sessionOnly) {
      // Classification only: never retain query/header/body/userinfo values or
      // call a Request/custom object's getters to inspect a forbidden request.
      let destination = 'not_reported';
      if (typeof url === 'string') {
        try {
          const parsed = new URL(url);
          const known = new Map([
            ['https://api.github.com/copilot_internal/v2/token', 'copilot_auth_token_exchange'],
            ['https://api.githubcopilot.com/models', 'capi_models_catalog'],
            ['https://api.githubcopilot.com/responses', 'capi_responses'],
            ['https://api.githubcopilot.com/chat/completions', 'capi_chat_completions'],
          ]);
          destination = known.get(parsed.origin + parsed.pathname) || 'other_http';
        } catch { destination = 'invalid_url'; }
      }
      blocked('capi_or_http', 'session_policy_http_refused', { destination, ...metadata.coordinates(url, init), forwarded: false });
    }
    const address = new URL(typeof url === 'string' || url instanceof URL ? url : url.url);
    const isResponses = /\/(?:v1\/)?responses\/?$/.test(address.pathname);
    const isModelRoute = isResponses || /\/chat\/completions\/?$/.test(address.pathname);
    if (!isModelRoute) return fetch(url, init);
    if (modelFree) {
      record('blocked', { boundary: 'capi', reason: 'wire_model_free_http_refused' });
      fail('wire_model_free_http_refused');
    }
    if (!isResponses || address.protocol !== 'https:' || address.username || address.password || address.search || address.hash ||
        !(address.hostname === 'api.githubcopilot.com' || address.hostname.endsWith('.githubcopilot.com')) ||
        init?.method?.toUpperCase() !== 'POST' || typeof init.body !== 'string') fail('wire_capi_transport_shape_refused');
    const stream = `http-${++httpNumber}`;
    if (Buffer.byteLength(init.body) > LIMIT) fail('wire_frame_limit');
    const headers = Object.fromEntries(new Headers(init.headers).entries());
    mask.learn(headers);
    const request = parseJson(init.body);
    raw('capi_request', { stream, url: address.origin + address.pathname, headers, delivery: 'attempted' }, request, init.body);
    // Exactly one original fetch, unchanged args, body, headers and AbortSignal.
    const response = await fetch(url, init);
    const responseHeaders = Object.fromEntries(response.headers.entries());
    mask.learn(responseHeaders);
    record('capi_headers', { stream, status: response.status, headers: responseHeaders });
    const isSse = (response.headers.get('content-type') || '').startsWith('text/event-stream');
    function responseValue(text) {
      try { return JSON.parse(text); }
      catch { record('wire_parse_error', { stream, reason: 'wire_response_json_invalid' }); return null; }
    }
    const parser = frames(text => {
      const lines = text.split(/\r?\n/);
      const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /, '')).join('\n');
      const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim() || 'message';
      const value = !data || data === '[DONE]' ? null : responseValue(data);
      raw('capi_event', { stream, event }, value, text);
    }, /\r?\n\r?\n/);
    let plain = '', finished = false;
    function chunk(part) {
      if (isSse) parser.feed(part);
      else { plain += Buffer.from(part).toString('base64') + '\n'; if (plain.length > LIMIT * 2) fail('wire_frame_limit'); }
    }
    function end() {
      if (finished) return;
      finished = true;
      if (isSse) parser.end();
      else {
        const text = Buffer.concat(plain.trim().split('\n').filter(Boolean).map(part => Buffer.from(part, 'base64'))).toString('utf8');
        raw('capi_body', { stream }, responseValue(text), text);
      }
      record('capi_end', { stream });
    }
    if (response.body) {
      const getReader = response.body.getReader.bind(response.body);
      response.body.getReader = function (...args) {
        const reader = getReader(...args);
        const read = reader.read.bind(reader);
        reader.read = async function (...readArgs) {
          const value = await read(...readArgs);
          if (value.value) chunk(value.value);
          if (value.done) end();
          return value;
        };
        return reader;
      };
    }
    const text = response.text.bind(response);
    response.text = async function () {
      const value = await text(); chunk(Buffer.from(value)); end(); return value;
    };
    record('capi_reader_instrumented', { stream });
    return response;
  }
  record('observer_installed', { model_free: modelFree, session_only: sessionOnly, native_binary_sha256: nativeSha256,
    entrypoint: options.entrypoint || 'fixture',
    hooks: ['native_spawn_stdio', 'capi_fetch_headers_body_stream'], observer_sha256: options.observerSha256 || 'fixture' });
  return { spawn: wrappedSpawn, fetch: wrappedFetch, fork: wrappedFork };
}

function activate() {
  const directory = process.env.GHCP_AHP_WIRE_DIR;
  if (!directory) return;
  const mode = process.env.GHCP_AHP_WIRE_MODE;
  if (!path.isAbsolute(directory) || !['model-free', 'connection', 'session-only'].includes(mode)) fail('wire_bootstrap_refused');
  const seeds = parseJson(process.env.GHCP_AHP_WIRE_SEEDS || '[]');
  delete process.env.GHCP_AHP_WIRE_SEEDS;
  const nativeBinary = process.env.GHCP_AHP_WIRE_NATIVE;
  const metadataSocket = process.env.GHCP_AHP_WIRE_METADATA_SOCKET;
  if (metadataSocket && (mode !== 'session-only' || !path.isAbsolute(metadataSocket) || !fs.lstatSync(metadataSocket).isSocket())) fail('metadata_socket_refused');
  if (crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, 'ghcp_ahp_metadata_client.cjs'))).digest('hex') !== process.env.GHCP_AHP_WIRE_METADATA_SHA256) fail('metadata_client_drift');
  const nativeSha256 = process.env.GHCP_AHP_WIRE_NATIVE_SHA256;
  const observerSha256 = crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');
  if (observerSha256 !== process.env.GHCP_AHP_WIRE_OBSERVER_SHA256) fail('wire_observer_drift');
  const forkEncoded = process.env.GHCP_AHP_WIRE_FORK_CONTRACT || '';
  if (crypto.createHash('sha256').update(forkEncoded).digest('hex') !== process.env.GHCP_AHP_WIRE_FORK_SHA256) fail('wire_fork_contract_drift');
  const forkContract = parseJson(forkEncoded);
  const output = fs.openSync(path.join(directory, `wire-${process.pid}.jsonl`), 'wx', 0o600);
  const childProcess = require('node:child_process');
  const wrapped = instrument({ spawn: childProcess.spawn, fetch: globalThis.fetch, fork: childProcess.fork }, {
    emit: line => fs.writeSync(output, line), modelFree: mode !== 'connection', sessionOnly: mode === 'session-only', seeds,
    metadataRequest: metadataSocket ? require('./ghcp_ahp_metadata_client.cjs').client(metadataSocket) : undefined,
    nativeBinary, nativeSha256, observerSha256, observerPath: __filename,
    forkContract, runtimeExecPath: process.execPath, parentArgv: process.argv, parentPid: process.pid,
    entrypoint: process.env.VSCODE_ESM_ENTRYPOINT || path.basename(process.argv[1] || ''),
    claimThread() {
      // Shared across observer/native-process restarts. Never release/reuse it.
      const claim = fs.openSync(path.join(directory, 'thread-start.claim'), 'wx', 0o600);
      fs.closeSync(claim);
    },
    verifyBinary(binary, expected) {
      if (crypto.createHash('sha256').update(fs.readFileSync(binary)).digest('hex') !== expected) fail('wire_native_binary_drift');
    },
  });
  childProcess.spawn = wrapped.spawn;
  childProcess.fork = wrapped.fork;
  syncBuiltinESMExports();
  globalThis.fetch = wrapped.fetch;
}

module.exports = { instrument, redactor, frames, READ_ONLY_RPC, safeArguments };
activate();
