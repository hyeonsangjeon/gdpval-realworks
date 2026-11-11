'use strict';

// Alternative zero-turn observation contract only. Never rewrite a native
// packet or bundle, enable a turn, or change the original read-only contract.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const modules = require('node:module');
const { fileURLToPath } = require('node:url');
const PROFILE = 'default_policy_unpatched';
const PIN = '2c33b50b16c472efe58357d1d2a8a5414bc23fbf';
const ARCHIVE = '65a713d95bb598310ad86db4daea28f9c3f9687b59ee9e57b3e7060a810bf916';
const UNPATCHED_BUNDLE = 'bf1c335134a145a8c2af6e00975c3320ef1ad21f542f6c07fdf1361e3cf94780';
const ENTRYPOINT = 'vs/platform/agentHost/node/agentHostMain';
const RELATIVE = 'out/' + ENTRYPOINT + '.js';
const RESOLVER_DEFAULTS = Object.freeze({ 'codex.permissionsPreset': 'default',
  'codex.approvalPolicy': 'on-request', 'codex.sandboxMode': 'workspace-write',
  'codex.networkAccessEnabled': false, 'codex.webSearchMode': 'disabled', 'codex.modelReasoningEffort': 'medium' });
const fail = code => { throw Object.assign(new Error(code), { code }); };
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);

function resolvedPolicy(values) {
  if (!values || values['codex.permissionsPreset'] !== 'default') fail('management_default_policy_readback_refused');
  const resolved = {};
  for (const [key, expected] of Object.entries(RESOLVER_DEFAULTS)) {
    const actual = Object.hasOwn(values, key) ? values[key] : 'not_reported';
    if (actual !== 'not_reported' && !same(actual, expected)) fail('management_default_policy_readback_refused');
    resolved[key] = actual;
  }
  return resolved; // Absent defaults stay absent observations, never filled in.
}

function threadRejections(message, modelFree) {
  const p = message?.params, config = p?.config, fields = [];
  const check = (field, accepted, expected, actual) => { if (!accepted) fields.push({ field, expected, actual: actual ?? 'absent' }); };
  check('modelFree', modelFree === true, true, modelFree);
  check('params.model', p?.model === 'gpt-5.6-sol', 'gpt-5.6-sol', p?.model);
  check('params.modelProvider', p?.modelProvider === 'vscode-proxy', 'vscode-proxy', p?.modelProvider);
  check('params.approvalPolicy', p?.approvalPolicy === 'on-request', 'on-request', p?.approvalPolicy);
  check('params.permissions', p?.permissions === 'vscode-workspace', 'vscode-workspace', p?.permissions);
  check('params.sandbox', p?.sandbox === undefined, 'absent', p?.sandbox);
  check('params.approvalsReviewer', p?.approvalsReviewer === 'user', 'user', p?.approvalsReviewer);
  check('params.config.web_search', config?.web_search === 'disabled', 'disabled', config?.web_search);
  check('params.allowProviderModelFallback', p?.allowProviderModelFallback === undefined || p.allowProviderModelFallback === false,
    'absent_or_false', p?.allowProviderModelFallback);
  check('params.config.model_context_window', !!config && (config.model_context_window === undefined || config.model_context_window === 1000000),
    'absent_or_1000000', config?.model_context_window);
  check('params.config.model_reasoning_effort', !!config && (config.model_reasoning_effort === undefined || config.model_reasoning_effort === 'max'),
    'absent_or_max', config?.model_reasoning_effort);
  check('params.config.mcp_servers', !!config && Object.keys(config.mcp_servers || {}).length === 0, 'absent_or_empty', config?.mcp_servers);
  check('id', ['string', 'number'].includes(typeof message?.id), 'string_or_number', message?.id);
  check('shape', !!message && !Object.hasOwn(message, 'result') && !Object.hasOwn(message, 'error'), 'request', 'invalid');
  return fields;
}

function readRegular(name, maximum = 256 * 1024 * 1024) {
  if (typeof name !== 'string' || !path.isAbsolute(name) || path.normalize(name) !== name || fs.realpathSync(name) !== name)
    fail('default_policy_runtime_path_refused');
  let at = '/';
  for (const part of name.split('/').filter(Boolean)) {
    at = path.join(at, part);
    if (fs.lstatSync(at).isSymbolicLink()) fail('default_policy_runtime_path_refused');
  }
  const fd = fs.openSync(name, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const before = fs.fstatSync(fd), raw = fs.readFileSync(fd), after = fs.fstatSync(fd);
    if (!before.isFile() || before.nlink !== 1 || raw.length < 1 || raw.length > maximum || raw.length !== before.size ||
        ['dev', 'ino', 'size', 'mtimeMs', 'ctimeMs'].some(key => before[key] !== after[key])) fail('default_policy_runtime_file_refused');
    return raw;
  } finally { fs.closeSync(fd); }
}

function validateContract(contract, forkContract) {
  const keys = ['schema', 'admission_profile', 'vscode_commit', 'server_archive_sha256', 'node', 'entry',
    'loader_sha256', 'state_root', 'challenge', 'patched_ghcp', 'patches_applied', 'synthetic', 'execution_allowed'];
  if (!contract || !same(Object.keys(contract).sort(), keys.sort()) || !contract.node || !contract.entry ||
      !same(Object.keys(contract.node).sort(), ['path', 'sha256']) || !same(Object.keys(contract.entry).sort(), ['path', 'sha256']) ||
      typeof contract.challenge !== 'string' || !/^[a-f0-9]{32}$/.test(contract.challenge) ||
      contract.state_root !== forkContract?.state_root || forkContract?.entrypoint !== ENTRYPOINT) fail('default_policy_unpatched_contract_refused');
  if (contract?.schema !== 'ghcp-default-unpatched-load-contract-v1' || contract.admission_profile !== PROFILE ||
      contract.vscode_commit !== PIN || contract.server_archive_sha256 !== ARCHIVE || contract.patched_ghcp !== false ||
      contract.execution_allowed !== false || !same(contract.patches_applied, []) || typeof contract.synthetic !== 'boolean' ||
      !contract.synthetic && contract.entry?.sha256 !== UNPATCHED_BUNDLE ||
      contract.loader_sha256 !== sha(readRegular(__filename)) || forkContract?.vscode_commit !== PIN ||
      forkContract?.files?.node?.path !== contract.node?.path || forkContract?.files?.node?.sha256 !== contract.node?.sha256 ||
      contract.entry?.path !== path.join(path.dirname(contract.node.path), RELATIVE) ||
      sha(readRegular(contract.node.path)) !== contract.node.sha256 || sha(readRegular(contract.entry.path)) !== contract.entry.sha256) {
    fail('default_policy_unpatched_runtime_refused');
  }
}

function installLoadObserver(options, record) {
  const contract = options.defaultPolicyContract;
  validateContract(contract, options.forkContract);
  if (options.patchedRuntime || options.modelFree !== true || options.sessionOnly !== true) fail('default_policy_mode_refused');
  if (options.entrypoint !== ENTRYPOINT) return;
  if (process.execPath !== contract.node.path || typeof modules.registerHooks !== 'function') fail('default_policy_loader_unavailable');
  let measured = false;
  modules.registerHooks({ load(url, context, nextLoad) {
    const location = new URL(url);
    if (location.protocol !== 'file:' || fileURLToPath(location) !== contract.entry.path) return nextLoad(url, context);
    if (location.search || location.hash || measured) fail('default_policy_load_alias_or_duplicate');
    const before = sha(readRegular(contract.entry.path));
    if (before !== contract.entry.sha256) fail('default_policy_before_load_mismatch');
    const loaded = nextLoad(url, context);
    const bytes = typeof loaded.source === 'string' ? Buffer.from(loaded.source) : ArrayBuffer.isView(loaded.source) ?
      Buffer.from(loaded.source.buffer, loaded.source.byteOffset, loaded.source.byteLength) : null;
    const after = sha(readRegular(contract.entry.path));
    if (loaded.format !== 'module' || !bytes || sha(bytes) !== before || after !== before) fail('default_policy_loaded_source_mismatch');
    record('default_policy_loaded', { schema: 'ghcp-default-unpatched-load-v1', admission_profile: PROFILE,
      contract_sha256: options.defaultPolicyContractSha256, pid: process.pid, ppid: process.ppid,
      loaded_source_sha256: sha(bytes), disk_before_sha256: before, disk_after_sha256: after,
      patched_ghcp: false, execution_allowed: false, phase: 'node_load_hook_before_evaluation' });
    measured = true;
    return loaded; // No replacement of loader bytes, policy or native traffic.
  } });
}

function identityDigest(value) {
  return { path_sha256: sha(value.path), realpath_sha256: sha(value.realpath),
    device: value.device, inode: value.inode, uid: value.uid };
}

function sandboxScope(result, binding, request, directoryIdentity) {
  const sandbox = result?.sandbox;
  const report = { schema: 'ghcp-default-unpatched-sandbox-scope-v1', admission_profile: PROFILE,
    status: 'refused', binding, reported_sandbox: sandbox?.type ?? 'not_reported',
    reported_writable_roots: sandbox?.writableRoots ?? 'not_reported',
    approval: result?.approvalPolicy ?? 'not_reported', network: sandbox?.networkAccess ?? 'not_reported',
    permission_profile: result?.activePermissionProfile?.id ?? 'not_reported',
    exclude_slash_tmp: sandbox?.excludeSlashTmp ?? 'not_reported',
    exclude_tmpdir_env_var: sandbox?.excludeTmpdirEnvVar ?? 'not_reported', root_identities: [] };
  try {
    if (binding?.status !== 'measured') fail('default_policy_tmpdir_unmeasured');
    const temporary = directoryIdentity(binding.job_tmpdir.path), workspace = directoryIdentity(request?.params?.cwd);
    if (!same(temporary, binding.job_tmpdir) || workspace.path !== path.join(binding.state_root, 'workspace') ||
        workspace.uid !== temporary.uid || request.params.runtimeWorkspaceRoots !== undefined &&
        !same(request.params.runtimeWorkspaceRoots, [workspace.path])) fail('default_policy_workspace_binding_refused');
    report.workspace_identity = identityDigest(workspace);
    report.tmpdir_at_reply = temporary;
    if (report.reported_sandbox !== 'workspaceWrite' || report.network !== false || report.approval !== 'on-request' ||
        report.permission_profile !== 'vscode-workspace' || report.exclude_slash_tmp !== true ||
        typeof report.exclude_tmpdir_env_var !== 'boolean') fail('default_policy_native_policy_refused');
    const roots = report.reported_writable_roots;
    if (!Array.isArray(roots) || roots.length > 2) fail('default_policy_roots_unreported_or_unbounded');
    const seen = new Set();
    for (const root of roots) {
      const actual = directoryIdentity(root);
      const role = same(actual, workspace) ? 'job_workspace' : same(actual, temporary) ? 'job_tmpdir' : null;
      if (!role || seen.has(role)) fail('default_policy_root_outside_job_or_duplicate');
      seen.add(role); report.root_identities.push({ role, ...identityDigest(actual) });
    }
    report.status = 'measured'; report.verdict = 'default_workspace_policy_observed';
  } catch (error) {
    report.reason = /^(?:default_policy|sandbox_scope)_[a-z_]+$/.test(error.message) ? error.message : 'default_policy_scope_unmeasured';
  }
  return report;
}

module.exports = { PROFILE, PIN, ARCHIVE, UNPATCHED_BUNDLE, ENTRYPOINT, RELATIVE, RESOLVER_DEFAULTS, resolvedPolicy,
  threadRejections, validateContract, installLoadObserver, sandboxScope, identityDigest };
