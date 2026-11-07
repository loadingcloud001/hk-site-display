// Keeps a copy of the notice page (never the data), so a screen that powers on, or is reloaded, while the
// site's internet or the server is down still opens the page. The page then shows 無法取得資料 and fetches the
// data by itself as soon as the network is back, with nobody touching the screen.
//
// The page always comes from the network when it answers (within PAGE_TIMEOUT_MS, with no server error), so
// this copy can never hold back a deploy. /api/ is never touched here.
// To remove this worker from every screen, deploy a sw.js that calls self.registration.unregister().
const CACHE = "hksd-page-v1";
const PAGE = "/";
const PAGE_TIMEOUT_MS = 8000;

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    fetch(PAGE, { cache: "no-store" })
      .then((response) => (response.ok ? response.text().then(remember) : undefined))
      .catch(() => undefined),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname === "/" || url.pathname === "/index.html") {
    let saving = Promise.resolve();
    const network = fetch(request).then((response) => {
      if (response.ok) saving = response.clone().text().then(remember);
      return response;
    });
    event.waitUntil(network.then(() => saving).catch(() => undefined));
    event.respondWith(page(network));
  } else if (url.pathname.startsWith("/assets/")) {
    // Named after their content, so a copy is always right.
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});

async function page(network) {
  const copy = await caches.match(PAGE);
  if (!copy) return network;
  try {
    const response = await Promise.race([network, new Promise((resolve) => setTimeout(resolve, PAGE_TIMEOUT_MS))]);
    if (response && response.status < 500) return response;
  } catch {
    // Offline, or the server is unreachable: use the copy.
  }
  return copy;
}

// Keep this version of the page and the files it names. The previous copy is replaced only once every file
// is stored, so the copy is never a page without its script.
async function remember(html) {
  const files = [...new Set([...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((match) => match[1]))];
  if (!files.some((file) => file.endsWith(".js"))) return; // not the notice page
  const cache = await caches.open(CACHE);
  for (const file of files) {
    if (await cache.match(file)) continue;
    const response = await fetch(file);
    if (!response.ok) return;
    await cache.put(file, response);
  }
  await cache.put(PAGE, new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } }));
  for (const request of await cache.keys()) {
    const path = new URL(request.url).pathname;
    if (path !== PAGE && !files.includes(path)) await cache.delete(request);
  }
}
