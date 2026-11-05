'use strict';

// Observer only: never replace source, rewrite native requests, or open admission.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { fileURLToPath } = require('node:url');
const modules = require('node:module');

const PIN = '2c33b50b16c472efe58357d1d2a8a5414bc23fbf';
const PATCH = 'a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb';
const RELATIVE = 'out/vs/platform/agentHost/node/agentHostMain.js';
const ENTRYPOINT = 'vs/platform/agentHost/node/agentHostMain';
const CONTRACT = 'GHCP_AHP_PATCHED_RUNTIME_CONTRACT';
const CONTRACT_SHA = 'GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256';
const LIMIT = 64 * 1024 * 1024;
const fail = code => { throw new Error(code); };
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const hex = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function sorted(value) {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])]));
  return value;
}
function safePath(value, directory = false) {
  if (typeof value !== 'string' || !path.isAbsolute(value) || path.normalize(value) !== value) fail('patched_runtime_path_refused');
  let info;
  try {
    if (fs.realpathSync(value) !== value || fs.lstatSync(value).isSymbolicLink()) fail('patched_runtime_path_refused');
    info = fs.statSync(value);
  } catch { fail('patched_runtime_path_refused'); }
  if (directory ? !info.isDirectory() : !info.isFile()) fail('patched_runtime_path_refused');
  return value;
}
function read(value, maximum = LIMIT) {
  safePath(value);
  const descriptor = fs.openSync(value, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const info = fs.fstatSync(descriptor);
    if (!info.isFile() || info.size <= 0 || info.size > maximum) fail('patched_runtime_file_refused');
    const bytes = fs.readFileSync(descriptor);
    if (bytes.length !== info.size || bytes.length > maximum) fail('patched_runtime_file_refused');
    return bytes;
  } finally { fs.closeSync(descriptor); }
}
function validate(contract, encoded) {
  const keys = ['schema', 'patched_ghcp', 'upstream_commit', 'patch_sha256', 'build_receipt_sha256',
    'runtime_bundle_sha256', 'runtime_bundle_path', 'runtime_relative_path', 'node_path', 'node_sha256',
    'loader_sha256', 'proof_directory', 'challenge', 'entrypoint', 'synthetic', 'execution_allowed', 'admission_allowed'];
  if (!contract || typeof contract !== 'object' || Array.isArray(contract) ||
      JSON.stringify(Object.keys(contract).sort()) !== JSON.stringify(keys.sort()) ||
      JSON.stringify(sorted(contract)) !== encoded ||
      contract.schema !== 'ghcp-patched-runtime-contract-v1' || contract.patched_ghcp !== true ||
      contract.upstream_commit !== PIN || contract.patch_sha256 !== PATCH ||
      contract.execution_allowed !== false || contract.admission_allowed !== false ||
      contract.runtime_relative_path !== RELATIVE || contract.entrypoint !== ENTRYPOINT ||
      typeof contract.synthetic !== 'boolean' || typeof contract.challenge !== 'string' || !/^[a-f0-9]{32}$/.test(contract.challenge) ||
      !['build_receipt_sha256', 'runtime_bundle_sha256', 'node_sha256', 'loader_sha256'].every(key => hex(contract[key]))) {
    fail('patched_runtime_contract_refused');
  }
  safePath(contract.node_path); safePath(contract.runtime_bundle_path); safePath(contract.proof_directory, true);
  if (path.basename(contract.node_path) !== 'node' ||
      path.join(path.dirname(contract.node_path), RELATIVE) !== contract.runtime_bundle_path ||
      path.basename(contract.proof_directory) !== 'patched-runtime' || path.basename(path.dirname(contract.proof_directory)) !== 'wire' ||
      (fs.statSync(contract.proof_directory).mode & 0o777) !== 0o700 ||
      (process.getuid && fs.statSync(contract.proof_directory).uid !== process.getuid())) fail('patched_runtime_path_refused');
  if (sha(read(__filename, 64 * 1024)) !== contract.loader_sha256 ||
      sha(read(contract.node_path, 256 * 1024 * 1024)) !== contract.node_sha256 ||
      sha(read(contract.runtime_bundle_path)) !== contract.runtime_bundle_sha256) fail('patched_runtime_hash_mismatch');
}

function activate({ modelFree, sessionOnly, entrypoint, forkContract }) {
  const encoded = process.env[CONTRACT], expected = process.env[CONTRACT_SHA];
  delete process.env[CONTRACT]; delete process.env[CONTRACT_SHA];
  if (encoded === undefined && expected === undefined) return null;
  if (modelFree !== true || sessionOnly !== true || typeof encoded !== 'string' || encoded.length > 65536 ||
      !hex(expected) || sha(encoded) !== expected) fail('patched_runtime_mode_or_contract_refused');
  let contract;
  try { contract = JSON.parse(encoded); } catch { fail('patched_runtime_json_refused'); }
  validate(contract, encoded);
  if (forkContract?.vscode_commit !== PIN || forkContract?.entrypoint !== ENTRYPOINT ||
      forkContract?.files?.node?.path !== contract.node_path || forkContract?.files?.node?.sha256 !== contract.node_sha256) {
    fail('patched_runtime_fork_binding_refused');
  }
  const result = { environment: { [CONTRACT]: encoded, [CONTRACT_SHA]: expected }, contractSha256: expected };
  // The validated parent only carries this immutable contract to the existing
  // guarded fork. Only the exact Agent Host child installs the source observer.
  if (entrypoint !== ENTRYPOINT) return result;
  if (safePath(process.execPath) !== contract.node_path || typeof modules.registerHooks !== 'function') {
    fail('patched_runtime_loader_unavailable');
  }
  let measured = false;
  modules.registerHooks({
    load(url, context, nextLoad) {
      const location = new URL(url);
      if (location.protocol !== 'file:' || fileURLToPath(location) !== contract.runtime_bundle_path) return nextLoad(url, context);
      if (location.search || location.hash || measured) fail('patched_runtime_load_alias_or_duplicate');
      const before = sha(read(contract.runtime_bundle_path));
      if (before !== contract.runtime_bundle_sha256) fail('patched_runtime_before_load_mismatch');
      let loaded;
      try { loaded = nextLoad(url, context); }
      catch { fail('patched_runtime_load_unmeasured'); }
      const bytes = typeof loaded.source === 'string' ? Buffer.from(loaded.source, 'utf8') :
        ArrayBuffer.isView(loaded.source) ? Buffer.from(loaded.source.buffer, loaded.source.byteOffset, loaded.source.byteLength) : null;
      if (loaded.format !== 'module' || !bytes || bytes.length === 0 || bytes.length > LIMIT) fail('patched_runtime_load_unmeasured');
      const actual = sha(bytes), after = sha(read(contract.runtime_bundle_path));
      if (actual !== contract.runtime_bundle_sha256 || after !== actual) fail('patched_runtime_loaded_source_mismatch');
      const proof = { schema: 'ghcp-patched-runtime-load-v1', patched_ghcp: true,
        upstream_commit: PIN, patch_sha256: PATCH, build_receipt_sha256: contract.build_receipt_sha256,
        runtime_contract_sha256: expected, loaded_relative_path: RELATIVE,
        loaded_source_sha256: actual, disk_before_sha256: before, disk_after_sha256: after,
        node_sha256: contract.node_sha256, loader_sha256: contract.loader_sha256,
        challenge_sha256: sha(contract.challenge), synthetic: contract.synthetic,
        phase: 'node_load_hook_before_evaluation', execution_allowed: false, pid: process.pid, ppid: process.ppid };
      safePath(contract.proof_directory, true);
      const output = path.join(contract.proof_directory, `load-${process.pid}.json`);
      const descriptor = fs.openSync(output, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
      try { fs.writeFileSync(descriptor, JSON.stringify(sorted(proof)) + '\n'); fs.fsyncSync(descriptor); }
      finally { fs.closeSync(descriptor); }
      measured = true;
      return loaded; // Exactly the loader's result: no byte rewriting or policy substitution.
    },
  });
  return result;
}

module.exports = { activate };
