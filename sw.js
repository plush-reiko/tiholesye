/* ===== Тихолесье · офлайн: при первом открытии кладёт игру в память телефона и дальше запускает её без сети ===== */
const CACHE = 'tiholesye-34fcdb81c0bc';     // сборка подставляет отпечаток игры: новая версия → новый кэш
const FILES = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png'];

// установка: скачать все файлы игры; cache: 'reload' — свежие с сервера, а не из обычного кэша браузера
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE)
    .then((c) => c.addAll(FILES.map((f) => new Request(f, { cache: 'reload' }))))
    .then(() => self.skipWaiting()));
});

// новая версия встала — старые копии больше не нужны
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith('tiholesye-') && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// сначала память телефона, сеть — только если файла там нет; так игра не ждёт интернет, даже когда он есть
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(req, { ignoreSearch: true }) || (req.mode === 'navigate' && await c.match('./index.html'));
    return hit || fetch(req);
  })());
});
