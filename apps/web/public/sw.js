const CACHE = 'kurilka-static-dev';
const PRECACHE = ['/', '/manifest.webmanifest', '/icon.svg', '/privacy.html', '/terms.html'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([
    self.clients.claim(),
    caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('kurilka-static-') && key !== CACHE).map(key => caches.delete(key)))),
  ]));
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;

  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok && url.origin === self.location.origin) {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy)));
      }
      return response;
    }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/')).then(cached => cached || Response.error())));
    return;
  }

  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    if (response.ok && url.origin === self.location.origin) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy)));
    }
    return response;
  }).catch(() => Response.error())));
});

self.addEventListener('push', event => {
  const text = event.data ? event.data.text() : 'Открой «Последнюю пачку», чтобы продолжить план.';
  event.waitUntil(self.registration.showNotification('Последняя пачка', { body: text, icon: '/icon.svg', tag: 'kurilka-support' }));
});
