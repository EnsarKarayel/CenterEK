'use strict';
(() => {
  const status = document.getElementById('connection');
  const update = () => {status.textContent = navigator.onLine ? 'Paneli açarak sunucuya bağlanabilirsiniz.' : 'Çevrimdışısınız. Bağlantı kurulduğunda yeniden deneyin.';};
  update();
  window.addEventListener('online', update);
  window.addEventListener('offline', update);
  // Installation UI never asks for Windows elevation or for a panel password.
  let prompt = null;
  const button = document.getElementById('install-panel');
  window.addEventListener('beforeinstallprompt', event => {event.preventDefault(); prompt = event; button.hidden = false;});
  button.addEventListener('click', async () => {
    const pending = prompt;
    if (!pending) return;
    prompt = null; button.hidden = true;
    try {await pending.prompt(); await pending.userChoice;} catch (_) { /* Browser menu installation remains available. */ }
  });
  window.addEventListener('appinstalled', () => {prompt = null; button.hidden = true;});
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/panel-worker.js', {scope: '/', updateViaCache: 'none'})
      .catch(() => {status.textContent = 'Paneli açabilirsiniz. Uygulama yükleme ve çevrimdışı ekranı şu anda kullanılamıyor.';});
  }
})();
