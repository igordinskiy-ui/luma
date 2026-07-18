const CACHE = 'kurilka-static-dev';
const PRECACHE = ['/', '/manifest.webmanifest', '/brand/luma-mark.svg', '/privacy.html', '/terms.html'];

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
  const fallback = { body: 'Открой «Последнюю пачку», чтобы продолжить план.', path: '/app' };
  let message = fallback;
  if (event.data) {
    try {
      const payload = event.data.json();
      const allowedPaths = ['/app', '/app/support', '/journal'];
      if (payload?.version === 1 && typeof payload.body === 'string' && allowedPaths.includes(payload.path)) {
        message = { body: payload.body.slice(0, 240), path: payload.path };
      }
    } catch {
      message = { body: event.data.text().slice(0, 240) || fallback.body, path: fallback.path };
    }
  }
  event.waitUntil(self.registration.showNotification('Последняя пачка', {
    body: message.body,
    icon: '/brand/luma-mark.svg',
    badge: '/brand/luma-mark.svg',
    tag: 'kurilka-support',
    data: { path: message.path },
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const allowedPaths = ['/app', '/app/support', '/journal'];
  const requestedPath = event.notification.data?.path;
  const path = allowedPaths.includes(requestedPath) ? requestedPath : '/app';
  const target = new URL(path, self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async clients => {
    const existing = clients.find(client => new URL(client.url).origin === self.location.origin);
    if (existing) {
      if ('navigate' in existing) await existing.navigate(target);
      return existing.focus();
    }
    return self.clients.openWindow(target);
  }));
});
