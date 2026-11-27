// Guarda la app y la última lista de normas para verlas sin internet.
const CACHE = "normas-v1";
const BASE = ["./", "index.html", "manifest.json", "icon-192.png", "icon-512.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Primero internet (para tener lo más nuevo); si no hay, lo guardado.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const clave = url.pathname.endsWith("normas.json") ? new Request(url.origin + url.pathname) : e.request;
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok) { const copia = r.clone(); caches.open(CACHE).then(c => c.put(clave, copia)); }
      return r;
    }).catch(() => caches.match(clave).then(r => r || caches.match("index.html")))
  );
});
