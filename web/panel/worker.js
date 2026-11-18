'use strict';
const CACHE = 'centerek-panel-public-v1';
const OFFLINE = '/panel/offline.html';
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const response = await fetch(OFFLINE, {credentials: 'omit', cache: 'no-store', redirect: 'error'});
    if (!response.ok || !response.headers.get('Content-Type')?.startsWith('text/html')) throw new Error('Offline page unavailable');
    const cache = await caches.open(CACHE);
    await cache.put(OFFLINE, response);
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('centerek-panel-public-') && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  // Never handle API requests, POSTs, exports, auth callbacks or another origin.
  if (request.method !== 'GET' || request.mode !== 'navigate' || url.origin !== self.location.origin
      || url.pathname.startsWith('/api/') || url.pathname.startsWith('/.auth/')) return;
  event.respondWith((async () => {
    try {return await fetch(request, {cache: 'no-store'});}
    catch (_) {
      const cache = await caches.open(CACHE);
      return await cache.match(OFFLINE) || new Response('CenterEK sunucusuna ulaşılamıyor.', {status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}});
    }
  })());
});
