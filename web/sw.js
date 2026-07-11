/* RoadLog PWA Service Worker — 항상 최신 셸 우선 (웹·모바일·홈화면 앱 공통) */
/** 배포 시 scripts/bump_build.py 또는 수동으로 반드시 올릴 것 */
const VERSION = "20260712-force-v21";
const CACHE = `roadlog-${VERSION}`;

/** 오프라인용 최소 자산만 (index/app/css 는 캐시에 묶지 않음) */
const PRECACHE = [
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/logo.svg",
];

function isShellPath(pathname) {
  return (
    pathname === "/" ||
    pathname === "/index.html" ||
    pathname === "/app.js" ||
    pathname === "/styles.css" ||
    pathname === "/sw.js" ||
    pathname === "/update.html" ||
    pathname === "/build.json" ||
    pathname === "/manifest.webmanifest" ||
    pathname.startsWith("/locales/") ||
    pathname.endsWith(".js") ||
    pathname.endsWith(".css") ||
    pathname.endsWith(".html") ||
    pathname.endsWith(".json") ||
    pathname.endsWith(".webmanifest")
  );
}

self.addEventListener("install", (event) => {
  // 대기 없이 즉시 활성화 후보로
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(
        PRECACHE.map((u) =>
          cache.add(u).catch(() => {
            /* ignore single failure */
          })
        )
      )
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // 모든 옛 캐시 삭제 (버전 불일치 전부)
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
      const clients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      clients.forEach((client) => {
        client.postMessage({ type: "SW_ACTIVATED", version: VERSION });
      });
    })()
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (data.type === "GET_VERSION" && event.source) {
    event.source.postMessage({ type: "SW_VERSION", version: VERSION });
  }
  if (data.type === "CLEAR_CACHES") {
    event.waitUntil(
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
    );
  }
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // API — 네트워크 only
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

  // 앱 셸·JS/CSS: 항상 네트워크 (캐시 저장 안 함 → 설치 앱도 최신)
  if (isShellPath(url.pathname)) {
    event.respondWith(
      fetch(req, { cache: "no-store" })
        .then((res) => res)
        .catch(async () => {
          const cached = await caches.match(req);
          if (cached) return cached;
          if (url.pathname === "/" || url.pathname.endsWith(".html")) {
            return (
              (await caches.match("/index.html")) ||
              new Response("오프라인", { status: 503 })
            );
          }
          return new Response("", { status: 503 });
        })
    );
    return;
  }

  // 아이콘 등: 네트워크 우선, 성공 시 캐시 갱신
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
