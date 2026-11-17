'use strict';
// Dedicated headless browser profile only. Never reads the user's browser session.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const [urlValue, folder] = process.argv.slice(2);
const url = new URL(urlValue);
if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/panel/' || url.search || url.hash) throw new Error('Exact HTTPS /panel/ URL required');
const output = path.resolve(folder);
if (fs.existsSync(output)) throw new Error('Use a new evidence folder');
fs.mkdirSync(output, {recursive: true});
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'CenterEK-PWA-Smoke-'));
const edge = path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'Microsoft/Edge/Application/msedge.exe');
const child = spawn(edge, ['--headless', '--disable-gpu', '--disable-background-networking', '--no-first-run',
  '--user-data-dir=' + temporary, '--remote-debugging-pipe', 'about:blank'],
  {windowsHide: true, stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
let serial = 0, buffered = '';
const pending = new Map();
child.stdio[4].on('data', data => {
  buffered += data.toString();
  for (let offset; (offset = buffered.indexOf('\0')) >= 0;) {
    const packet = buffered.slice(0, offset); buffered = buffered.slice(offset + 1);
    if (!packet) continue;
    const message = JSON.parse(packet);
    if (pending.has(message.id)) {
      const {resolve, reject, timer} = pending.get(message.id); pending.delete(message.id); clearTimeout(timer);
      message.error ? reject(new Error(message.error.message)) : resolve(message.result);
    }
  }
});
function call(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++serial;
    const timer = setTimeout(() => {pending.delete(id); reject(new Error('Browser command timeout: ' + method));}, 30000);
    pending.set(id, {resolve, reject, timer});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  const report = {ok: false, url: url.href, dedicated_profile: true, authenticated_login: 'pending-user-acceptance'};
  try {
    const {targetId} = await call('Target.createTarget', {url: 'about:blank'});
    const {sessionId} = await call('Target.attachToTarget', {targetId, flatten: true});
    const command = (method, params) => call(method, params, sessionId);
    await command('Page.enable'); await command('Network.enable'); await command('Runtime.enable');
    const evaluate = async expression => {
      const result = await command('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
      if (result.exceptionDetails) throw new Error('Browser evaluation failed');
      return result.result.value;
    };
    async function navigate(address, expected) {
      await command('Page.navigate', {url: address});
      for (let attempt = 0; attempt < 80; attempt++) {
        const text = await evaluate('document.body?.innerText || ""');
        if (text.includes(expected)) return;
        await sleep(250);
      }
      throw new Error('Expected browser page did not load');
    }
    await navigate(url.href, 'Paneli aç');
    report.service_worker = await evaluate('(async()=>{const r=await navigator.serviceWorker.ready; return r.active?.scriptURL})()');
    assert.equal(report.service_worker, url.origin + '/panel-worker.js');
    const manifest = await command('Page.getAppManifest');
    assert.equal(manifest.url, url.origin + '/panel/manifest.webmanifest');
    assert.equal(manifest.errors.length, 0);
    report.manifest_valid = true;
    report.installability_errors = (await command('Page.getInstallabilityErrors')).installabilityErrors;
    assert.deepEqual(report.installability_errors, []);
    const cacheKeys = await evaluate('(async()=>{const result=[]; for(const name of await caches.keys()){const cache=await caches.open(name); for(const r of await cache.keys())result.push(new URL(r.url).pathname)}return result})()');
    assert.deepEqual(cacheKeys, ['/panel/offline.html']); report.cached_paths = cacheKeys;
    // Reload under the active worker, then emulate offline in BOTH network targets.
    await navigate(url.href, 'Paneli aç');
    assert.equal(await evaluate('Boolean(navigator.serviceWorker.controller)'), true);
    const {targetInfos} = await call('Target.getTargets');
    const worker = targetInfos.find(target => target.type === 'service_worker' && target.url === report.service_worker);
    assert.ok(worker, 'Active service worker browser target required');
    const workerSession = (await call('Target.attachToTarget', {targetId: worker.targetId, flatten: true})).sessionId;
    await call('Network.enable', {}, workerSession);
    const image = await command('Page.captureScreenshot', {format: 'png'});
    fs.writeFileSync(path.join(output, 'azure-panel.png'), Buffer.from(image.data, 'base64'));
    report.stage = 'offline_navigation';
    await call('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1}, workerSession);
    await command('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await navigate(url.href, 'Sunucuya ulaşılamıyor'); report.offline_fallback = true;
    report.stage = 'online_recovery';
    await call('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1}, workerSession);
    await command('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await navigate(url.href, 'Paneli aç'); report.online_recovery = true;
    report.ok = true;
    report.stage = 'completed';
  } catch (error) {
    report.error = error.message;
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    try {await call('Browser.close');} catch (_) {}
    child.kill();
    // Only the newly created, known profile below the OS temporary directory.
    if (path.dirname(temporary) === path.resolve(os.tmpdir()) && path.basename(temporary).startsWith('CenterEK-PWA-Smoke-')) {
      try {fs.rmSync(temporary, {recursive: true, force: true});} catch (_) {}
    }
    console.log(JSON.stringify(report));
  }
})().catch(error => {child.kill(); console.error(error.message); process.exitCode = 1;});
