// 옛 운행일지 PWA 서비스워커를 스스로 제거한다.
// 이미 앱을 설치한 브라우저가 옛 화면에 묶이지 않게 하는 용도.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) await caches.delete(key);
    await self.registration.unregister();
    for (const client of await self.clients.matchAll({ type: 'window' })) {
      client.navigate(client.url);
    }
  })());
});
