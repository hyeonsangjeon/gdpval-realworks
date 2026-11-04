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

function instrument({ spawn, fetch, fork }, options) {
  const { emit, nativeBinary, nativeSha256, modelFree, synthetic = false, seeds = [] } = options;
  const mask = redactor(seeds);
  let sequence = 0, bytes = 0, ipcNumber = 0, httpNumber = 0;
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
  function requestAllowed(message) {
    if (modelFree && (!READ_ONLY_RPC.has(message.method) || Object.hasOwn(message, 'result') || Object.hasOwn(message, 'error'))) {
      record('blocked', { boundary: 'native_ipc', reason: 'wire_model_free_rpc_refused' });
      fail('wire_model_free_rpc_refused');
    }
  }
  function wrappedSpawn(command, args, settings) {
    if (path.resolve(String(command)) !== nativeBinary || !Array.isArray(args) || args[0] !== 'app-server') {
      return spawn(command, args, settings);
    }
    if (options.verifyBinary) options.verifyBinary(nativeBinary, nativeSha256);
    const stream = `ipc-${++ipcNumber}`;
    // Do not leak diagnostic bootstrap data or recursively preload tool children.
    const env = { ...(settings?.env || process.env) };
    mask.learn({ apiKey: env.OPENAI_API_KEY });
    for (const key of Object.keys(env)) if (key.startsWith('GHCP_AHP_WIRE_') || key === 'NODE_OPTIONS') delete env[key];
    const child = spawn(command, args, { ...settings, env });
    record('native_started', { stream, native_binary_sha256: nativeSha256 });
    const outgoing = frames(text => {
      const value = parseJson(text);
      requestAllowed(value); // Before the original write, including batched lines.
      raw('ipc_request', { stream, delivery: 'attempted' }, value, text);
    }, /\r?\n/);
    const incoming = frames(text => raw('ipc_response', { stream }, parseJson(text), text), /\r?\n/);
    const originalWrite = child.stdin.write;
    function inspectOutgoing(chunk) {
      // The pinned client writes complete newline-delimited messages. Never
      // forward a partial free-mode packet: a child could parse it on EOF.
      if (modelFree && !Buffer.from(chunk).toString('utf8').endsWith('\n')) fail('wire_model_free_partial_rpc_refused');
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
    if (settings?.env?.VSCODE_ESM_ENTRYPOINT !== 'vs/platform/agentHost/node/agentHostMain') return fork(modulePath, args, settings);
    if (!Array.isArray(args) || path.resolve(modulePath) !== options.bootstrapForkPath || !options.observerPath) fail('wire_agent_fork_refused');
    // VS Code intentionally strips NODE_OPTIONS from forks. Add only this
    // hash-bound observer as an explicit execArgv, never restore arbitrary options.
    const env = { ...settings.env, GHCP_AHP_WIRE_SEEDS: JSON.stringify(seeds) };
    const execArgv = [...(settings.execArgv || []), '--require', options.observerPath];
    record('agent_fork_instrumented');
    return fork(modulePath, args, { ...settings, env, execArgv });
  }
  async function wrappedFetch(url, init) {
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
  record('observer_installed', { model_free: modelFree, native_binary_sha256: nativeSha256,
    entrypoint: options.entrypoint || 'fixture',
    hooks: ['native_spawn_stdio', 'capi_fetch_headers_body_stream'], observer_sha256: options.observerSha256 || 'fixture' });
  return { spawn: wrappedSpawn, fetch: wrappedFetch, fork: wrappedFork };
}

function activate() {
  const directory = process.env.GHCP_AHP_WIRE_DIR;
  if (!directory) return;
  const mode = process.env.GHCP_AHP_WIRE_MODE;
  if (!path.isAbsolute(directory) || !['model-free', 'connection'].includes(mode)) fail('wire_bootstrap_refused');
  const seeds = parseJson(process.env.GHCP_AHP_WIRE_SEEDS || '[]');
  delete process.env.GHCP_AHP_WIRE_SEEDS;
  const nativeBinary = process.env.GHCP_AHP_WIRE_NATIVE;
  const nativeSha256 = process.env.GHCP_AHP_WIRE_NATIVE_SHA256;
  const observerSha256 = crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');
  if (observerSha256 !== process.env.GHCP_AHP_WIRE_OBSERVER_SHA256) fail('wire_observer_drift');
  const output = fs.openSync(path.join(directory, `wire-${process.pid}.jsonl`), 'wx', 0o600);
  const childProcess = require('node:child_process');
  const wrapped = instrument({ spawn: childProcess.spawn, fetch: globalThis.fetch, fork: childProcess.fork }, {
    emit: line => fs.writeSync(output, line), modelFree: mode === 'model-free', seeds,
    nativeBinary, nativeSha256, observerSha256, observerPath: __filename,
    bootstrapForkPath: process.env.GHCP_AHP_WIRE_BOOTSTRAP,
    entrypoint: process.env.VSCODE_ESM_ENTRYPOINT || path.basename(process.argv[1] || ''),
    verifyBinary(binary, expected) {
      if (crypto.createHash('sha256').update(fs.readFileSync(binary)).digest('hex') !== expected) fail('wire_native_binary_drift');
    },
  });
  childProcess.spawn = wrapped.spawn;
  childProcess.fork = wrapped.fork;
  syncBuiltinESMExports();
  globalThis.fetch = wrapped.fetch;
}

module.exports = { instrument, redactor, frames, READ_ONLY_RPC };
activate();
