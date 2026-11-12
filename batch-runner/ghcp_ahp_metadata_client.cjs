'use strict';
// Unix-domain transport only. No DNS, TCP, TLS or original fetch from the host.
const net = require('node:net');
const USER_URL = 'https://api.github.com/copilot_internal/user';
const MODEL_URLS = new Set([
  'https://api.githubcopilot.com/models', 'https://api.individual.githubcopilot.com/models',
  'https://api.business.githubcopilot.com/models', 'https://api.enterprise.githubcopilot.com/models',
]);
const MAX_BODY = 2 * 1024 * 1024;
function coordinates(url, init) {
  let host = 'not_reported', pathname = 'not_reported';
  if (typeof url === 'string') {
    try { const address = new URL(url); host = address.hostname; pathname = address.pathname; } catch {}
  }
  return { method: typeof init?.method === 'string' ? init.method : 'GET', host, path: pathname, status: null };
}
function request(url, init) {
  if (typeof url !== 'string' || (url !== USER_URL && !MODEL_URLS.has(url)) ||
      (init?.method !== undefined && init.method !== 'GET') || init?.body !== undefined ||
      (init?.redirect !== undefined && init.redirect !== 'error')) throw new Error('metadata_request_refused');
  const headers = Object.fromEntries(new Headers(init?.headers).entries());
  if (typeof headers.authorization !== 'string') throw new Error('metadata_auth_missing');
  return { method: 'GET', url, headers };
}
function client(socketPath) {
  return message => new Promise((resolve, reject) => {
    const socket = net.createConnection({ path: socketPath });
    let data = Buffer.alloc(0), done = false;
    const fail = () => { if (!done) { done = true; socket.destroy(); reject(new Error('metadata_socket_refused')); } };
    socket.setTimeout(15000, fail);
    socket.on('error', fail);
    socket.on('connect', () => socket.write(JSON.stringify(message) + '\n'));
    socket.on('data', chunk => {
      data = Buffer.concat([data, chunk]);
      if (data.length > 3 * 1024 * 1024) return fail();
      if (!data.includes(10)) return;
      try {
        const value = JSON.parse(data.toString('utf8'));
        if (value.error || !Number.isInteger(value.status) || value.status < 100 || value.status > 599 ||
            typeof value.body_base64 !== 'string' || typeof value.external_request !== 'boolean') return fail();
        const body = Buffer.from(value.body_base64, 'base64');
        if (body.length > MAX_BODY || body.toString('base64') !== value.body_base64) return fail();
        done = true; socket.end(); resolve({ ...value, body });
      } catch { fail(); }
    });
    socket.on('end', () => { if (!done) fail(); });
  });
}
module.exports = { request, coordinates, client, USER_URL, MODEL_URLS };
