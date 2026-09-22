// 离线缓存。装一次之后断网也能开（飞机关、地铁里都行）。
// 策略是 stale-while-revalidate：先拿缓存（快、离线可用），同时后台去取新的塞回缓存。
// 所以**改完 index.html 不用改版本号**——第一次打开还是旧的，第二次就是新的。
var CACHE = 'cet-vocab.v2';
var ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-512.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  // CACHE 改过名就得把上一份删掉，不然它会永远占着手机的存储
  e.waitUntil(
    caches.keys()
      .then(function (ks) {
        return Promise.all(ks.map(function (k) { return k === CACHE ? null : caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    caches.open(CACHE).then(function (c) {
      return c.match(e.request).then(function (hit) {
        var net = fetch(e.request).then(function (res) {
          if (res && res.ok) c.put(e.request, res.clone());
          return res;
        }).catch(function () { return hit; });
        return hit || net;
      });
    })
  );
});
