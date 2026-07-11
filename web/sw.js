/* RoadLog PWA Service Worker — always prefer fresh shell, keep offline fallback */
/** 배포마다 올리면 설치 앱이 새 SW를 잡고 갱신됩니다 */
const VERSION = "20260711-v13";
const CACHE = `roadlog-${VERSION}`;

const PRECACHE = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/logo.svg",
];

/** 네트워크 우선 — 옛 캐시에 막혀 UI가 남는 것 방지 */
function isNetworkFirst(pathname) {
  return (
    pathname === "/" ||
    pathname === "/index.html" ||
    pathname === "/app.js" ||
    pathname === "/styles.css" ||
    pathname === "/sw.js" ||
    pathname === "/manifest.webmanifest" ||
    pathname.startsWith("/locales/") ||
    pathname.endsWith(".js") ||
    pathname.endsWith(".css") ||
    pathname.endsWith(".json") ||
    pathname.endsWith(".html") ||
    pathname.endsWith(".webmanifest")
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
      .then(() =>
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
          clients.forEach((client) => {
            client.postMessage({ type: "SW_ACTIVATED", version: VERSION });
          });
        })
      )
  );
});

/** 클라이언트가 새 버전 즉시 적용 요청 */
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (data.type === "GET_VERSION" && event.source) {
    event.source.postMessage({ type: "SW_VERSION", version: VERSION });
  }
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // API — 네트워크만 (오프라인 시 JSON 안내)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req).catch(
        () =>
          new Response(JSON.stringify({ detail: "오프라인 상태입니다." }), {
            status: 503,
            headers: { "Content-Type": "application/json; charset=utf-8" },
          })
      )
    );
    return;
  }

  if (url.origin !== self.location.origin) return;

  // 앱 셸·JS/CSS/locale: 네트워크 우선, 실패 시 캐시
  if (isNetworkFirst(url.pathname)) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((c) => c || caches.match("/index.html")))
    );
    return;
  }

  // 아이콘 등: 캐시 우선, 백그라운드 갱신
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => cached || caches.match("/index.html"));
      return cached || network;
    })
  );
});
