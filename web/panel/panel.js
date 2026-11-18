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
  const help = document.getElementById('install-help');
  const standalone = window.matchMedia('(display-mode: standalone)');
  let installed = standalone.matches || navigator.standalone === true;
  const showInstalled = () => {
    prompt = null; button.hidden = true;
    help.textContent = 'CenterEK Panel uygulama olarak açık veya bu tarayıcıda yükleme tamamlandı. Paneli aç düğmesiyle devam edebilirsiniz.';
  };
  if (installed) showInstalled();
  standalone.addEventListener('change', event => {
    if (event.matches) {installed = true; showInstalled();}
  });
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    if (installed) return;
    prompt = event; button.hidden = false;
    help.textContent = 'CenterEK Paneli Başlat menüsünden açabilmek için yükleme düğmesini kullanın.';
  });
  button.addEventListener('click', async () => {
    const pending = prompt;
    if (!pending) return;
    prompt = null; button.hidden = true;
    try {
      await pending.prompt();
      const choice = await pending.userChoice;
      if (choice.outcome === 'accepted') {installed = true; showInstalled();}
      else help.textContent = 'Yükleme ertelendi. Paneli tarayıcıdan açabilir veya daha sonra tarayıcı menüsünden yükleyebilirsiniz.';
    } catch (_) {
      if (!installed) help.textContent = 'Yükleme penceresi açılamadı. Tarayıcı menüsünden yüklemeyi deneyebilir veya Paneli aç ile devam edebilirsiniz.';
    }
  });
  window.addEventListener('appinstalled', () => {installed = true; showInstalled();});
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/panel-worker.js', {scope: '/', updateViaCache: 'none'})
      .catch(() => {status.textContent = 'Paneli açabilirsiniz. Uygulama yükleme ve çevrimdışı ekranı şu anda kullanılamıyor.';});
  }
})();
