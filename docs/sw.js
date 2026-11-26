// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
//
// This source code is licensed under the license found in the
// LICENSE file in the root directory of this source tree.

/* SCALE4D page cache. The department server sends no Cache-Control or Expires header (mod_headers and mod_expires
   are not available), so every visit re-validated every file. This worker answers versioned requests (any URL with a
   ?v= / &v= parameter: scenes, thumbnails, figures, scripts) from its own cache after their first download. Videos and
   range requests always go to the network. Registered as sw.js?v=<V> from js/main.js; a new V opens a new cache and
   deletes the old ones, so a deploy never serves stale files. */
const CACHE = "scale4d-" + (new URL(self.location.href).searchParams.get("v") || "0");

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith("scale4d-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.method !== "GET" || r.headers.has("range")) return;
  const u = new URL(r.url);
  if (u.origin !== self.location.origin || !u.searchParams.has("v") || /\.(mp4|webm)$/i.test(u.pathname)) return;
  e.respondWith(caches.open(CACHE).then((c) => c.match(r).then((hit) => hit || fetch(r).then((res) => {
    if (res.status === 200 && res.type === "basic") c.put(r, res.clone()).catch(() => {});
    return res;
  }))));
});
