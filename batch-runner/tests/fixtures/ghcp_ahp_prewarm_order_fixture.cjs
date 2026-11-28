'use strict';

// Only the already hash-bound patch's pure ready hook is evaluated in a VM.
// This does not load VS Code/Codex or execute a model/runtime on the local host.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const raw = fs.readFileSync(process.argv[2]);
assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),
  'a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb');
const text = raw.toString();
const lines = text.split('\n');
const first = lines.findIndex(line => line === '+\t\tonChatConfigurationReady: (chat, context) => {');
assert(first > 0);
const last = lines.findIndex((line, index) => index > first && line === '+\t\t},');
assert(last > first);
let hook = lines.slice(first, last + 1).map(line => {
  assert(line.startsWith('+'));
  return line.slice(1);
}).join('\n').replace(/^\s*onChatConfigurationReady: /, '').replace(/,$/, '');
const scenario = process.argv[3];
if (scenario === 'without-config-guard') {
  hook = hook.replace('|| this._configValues(session.owner.get(), chat) === undefined', '');
} else if (scenario === 'without-one-shot') {
  hook = hook.replace('|| session.prewarmScheduled', '');
}
const requested = {'codex.approvalPolicy': 'untrusted', 'codex.sandboxMode': 'read-only',
  'codex.networkAccessEnabled': false, 'codex.webSearchMode': 'disabled', 'codex.modelReasoningEffort': 'max'};
const sessions = new Map(), configurations = new Map(), events = [];
const host = {
  _sessions: sessions,
  _resolveConversationSession: chat => chat,
  _configValues: (owner, chat) => configurations.get(chat),
  _schedulePrewarm: session => {
    const config = configurations.get(session.id);
    assert.deepEqual(config, requested, 'prewarm must never read absent/default policy');
    events.push({kind: 'prewarm', chat: session.id, policy: {...config}});
  },
};
const notify = new vm.Script('(function () { return (' + hook + '); }).call(host)').runInNewContext(
  {host, AgentSession: {id: uri => uri}}, {timeout: 500});
function session(id, extra = {}) {
  const value = {id, owner: {get: () => id}, disposed: false, prewarmClaimed: false,
    threadId: undefined, currentTurnId: undefined, materializePromise: undefined, ...extra};
  sessions.set(id, value);
  return value;
}
function publish(id) {
  configurations.set(id, {...requested});
  events.push({kind: 'config_published', chat: id});
}
for (const id of ['first', 'second']) {
  session(id);
  const before = events.length;
  notify(id, {});
  assert.equal(events.length, before, 'a deferred chat must not prewarm before state publication');
  publish(id);
  notify(id, {});
  notify(id, {});
  assert.equal(events.filter(row => row.chat === id && row.kind === 'prewarm').length, 1, 'prewarm is one-shot');
}
for (const [field, value] of [['disposed', true], ['prewarmClaimed', true], ['threadId', 'existing'],
  ['currentTurnId', 'existing'], ['materializePromise', {}]]) {
  const id = 'blocked-' + field;
  session(id, {[field]: value});
  publish(id);
  const before = events.length;
  notify(id, {});
  assert.equal(events.length, before, 'existing lifecycle gate must not be bypassed');
}
notify('missing-session', {});
const actual = events.filter(row => ['first', 'second'].includes(row.chat));
assert.deepEqual(actual.map(row => row.kind), ['config_published', 'prewarm', 'config_published', 'prewarm']);
console.log(JSON.stringify({synthetic: true, execution_allowed: false, sdk_or_host_executed: false,
  config_before_prewarm: true, native_requests: 0, events: actual, lifecycle_refusals: 6}));
