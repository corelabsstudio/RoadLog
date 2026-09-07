// 로드로그 서비스워커 — 설치가 되게 하는 것이 목적이다.
// 🛑 캐시를 쌓지 않는다. 배포해도 옛 화면이 남는 사고를 막기 위해서다.
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // 옛 운행일지 PWA 가 남긴 캐시를 털어 낸다
    for (const key of await caches.keys()) await caches.delete(key);
    await self.clients.claim();
  })());
});

// 크롬은 fetch 핸들러가 있어야 설치를 허용한다. 가로채지 않고 그대로 흘려보낸다.
self.addEventListener('fetch', () => {});
