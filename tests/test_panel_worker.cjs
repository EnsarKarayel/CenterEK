'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const handlers = {};
const saved = new Map();
const deleted = [];
const calls = [];
let failNetwork = false;
const cache = {put: async (key, value) => saved.set(key, value), match: async key => saved.get(key)};
const context = {
  URL, Response,
  self: {location: {origin: 'https://panel.example'}, addEventListener: (name, fn) => handlers[name] = fn,
    skipWaiting: async () => {}, clients: {claim: async () => {}}},
  caches: {open: async () => cache, keys: async () => ['centerek-panel-public-old', 'unrelated-app'], delete: async key => deleted.push(key)},
  fetch: async (request, options) => {
    calls.push({request, options});
    if (failNetwork) throw new Error('offline');
    return new Response(typeof request === 'string' ? 'public offline page' : 'private live dashboard', {headers: {'Content-Type': 'text/html'}});
  }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/panel/worker.js'), 'utf8'), context);
async function lifecycle(name) {let pending; handlers[name]({waitUntil: value => pending = value}); await pending;}
function request(url, mode = 'navigate', method = 'GET') {
  let pending;
  handlers.fetch({request: {url, mode, method}, respondWith: response => pending = response});
  return pending;
}
(async () => {
  await lifecycle('install');
  assert.deepEqual([...saved.keys()], ['/panel/offline.html']);
  assert.equal(calls[0].options.credentials, 'omit');
  assert.equal(calls[0].options.redirect, 'error');
  await lifecycle('activate');
  assert.deepEqual(deleted, ['centerek-panel-public-old']);
  for (const url of ['https://panel.example/api/status', 'https://panel.example/api/report.csv',
    'https://panel.example/.auth/login/aad', 'https://login.microsoftonline.com/tenant']) {
    assert.equal(request(url), undefined, url);
  }
  assert.equal(request('https://panel.example/api/login', 'cors', 'POST'), undefined);
  assert.equal(request('https://panel.example/app.js', 'no-cors'), undefined);
  let response = await request('https://panel.example/');
  assert.equal(await response.text(), 'private live dashboard');
  assert.equal(calls.at(-1).options.cache, 'no-store');
  assert.deepEqual([...saved.keys()], ['/panel/offline.html'], 'Private navigation must never enter the cache');
  failNetwork = true;
  response = await request('https://panel.example/');
  assert.equal(await response.text(), 'public offline page');
  saved.clear();
  response = await request('https://panel.example/');
  assert.equal(response.status, 503);
  console.log('Panel worker privacy, auth exclusions and offline fallback passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
