'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function browser({standalone = false, workerFails = false} = {}) {
  const handlers = {}, elements = {}, display = {matches: standalone, addEventListener() {}};
  for (const id of ['connection', 'install-panel', 'install-help']) {
    elements[id] = {hidden: id === 'install-panel', textContent: '', addEventListener(name, fn) {this[name] = fn;}};
  }
  const navigator = {onLine: true, serviceWorker: {register: async () => {
    if (workerFails) throw new Error('registration failed');
  }}};
  vm.runInNewContext(fs.readFileSync('web/panel/panel.js', 'utf8'), {
    document: {getElementById: id => elements[id]}, navigator,
    window: {isSecureContext: true, matchMedia: () => display, addEventListener: (name, fn) => handlers[name] = fn}
  });
  return {handlers, elements, navigator};
}
(async () => {
  let page = browser({standalone: true});
  assert.match(page.elements['install-help'].textContent, /uygulama olarak/);
  page.handlers.beforeinstallprompt({preventDefault() {}});
  assert.equal(page.elements['install-panel'].hidden, true);
  for (const outcome of ['accepted', 'dismissed', 'failure']) {
    page = browser();
    let prompts = 0;
    page.handlers.beforeinstallprompt({preventDefault() {}, prompt: async () => {
      prompts++; if (outcome === 'failure') throw new Error('prompt failed');
    }, userChoice: Promise.resolve({outcome})});
    assert.equal(page.elements['install-panel'].hidden, false);
    await page.elements['install-panel'].click();
    await page.elements['install-panel'].click();
    assert.equal(prompts, 1, 'consumed install event cannot be prompted twice');
    assert.equal(page.elements['install-panel'].hidden, true);
    assert.match(page.elements['install-help'].textContent,
      outcome === 'accepted' ? /yükleme tamamlandı/ : outcome === 'dismissed' ? /ertelendi/ : /açılamadı/);
  }
  page = browser({workerFails: true});
  await new Promise(resolve => setImmediate(resolve));
  assert.match(page.elements.connection.textContent, /kullanılamıyor/);
  page.navigator.onLine = false;
  page.handlers.offline();
  assert.match(page.elements.connection.textContent, /Çevrimdışısınız/);
  page.handlers.appinstalled();
  assert.match(page.elements['install-help'].textContent, /yükleme tamamlandı/);
  console.log('PWA installation, dismissal, failed prompt and offline behavior passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
