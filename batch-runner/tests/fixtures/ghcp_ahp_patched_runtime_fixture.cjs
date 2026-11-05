'use strict';
// Inert module-loading fixture. No Agent Host, Codex SDK, session, network or model.
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const modules = require('node:module');
const runtime = require('../../ghcp_ahp_patched_runtime.cjs');
const scenario = process.argv[2];
const contract = JSON.parse(process.env.GHCP_AHP_PATCHED_RUNTIME_CONTRACT);
const forkContract = { vscode_commit: contract.upstream_commit, entrypoint: contract.entrypoint,
  files: { node: { path: contract.node_path, sha256: contract.node_sha256 } } };

async function main() {
  if (scenario === 'no_hooks') modules.registerHooks = undefined;
  if (['rewrite_source', 'missing_source', 'wrong_format'].includes(scenario)) {
    modules.registerHooks({ load(url, context, next) {
      const loaded = next(url, context);
      if (url !== pathToFileURL(contract.runtime_bundle_path).href) return loaded;
      if (scenario === 'rewrite_source') return { ...loaded, source: Buffer.from('export const fixtureOnly = false;\n') };
      if (scenario === 'missing_source') return { ...loaded, source: null };
      return { ...loaded, format: 'commonjs' };
    } });
  }
  runtime.activate({ modelFree: scenario !== 'paid_mode', sessionOnly: true,
    entrypoint: scenario === 'wrong_entrypoint' ? 'server-main' : contract.entrypoint, forkContract });
  if (scenario === 'before_load_drift') fs.appendFileSync(contract.runtime_bundle_path, '// changed after registration\n');
  let loaded = false;
  if (scenario !== 'no_load') {
    const url = pathToFileURL(contract.runtime_bundle_path).href + (scenario === 'query_alias' ? '?alternate=1' : '');
    const value = await import(url);
    if (value.fixtureOnly !== true) throw new Error('fixture_module_invalid');
    loaded = true;
  }
  if (scenario === 'after_load_drift') fs.appendFileSync(contract.runtime_bundle_path, '// changed after evaluation\n');
  process.stdout.write(JSON.stringify({ pid: process.pid, ppid: process.ppid, loaded, synthetic: true,
    sessions: 0, turns: 0, model_calls: 0 }));
}
main().catch(error => { console.error(error.message); process.exitCode = 2; });
