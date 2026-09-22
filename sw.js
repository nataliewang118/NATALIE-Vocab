// 离线缓存。装一次之后断网也能开（飞机上、地铁里都行）。
//
// ⚠️ 以前用的是 stale-while-revalidate，两个毛病叠在一起：
//   1. 天生"改完要打开两次才生效"——第一次给你缓存里的旧的，后台再去取新的；
//   2. GitHub Pages 给 HTML 发的 Cache-Control 是 max-age=600，SW 后台那次 fetch
//      **会命中浏览器自己的 HTTP 缓存**，于是十几分钟内怎么刷都刷不出新的。
//
// 现在改成 network-first：在线时每次都去问服务器（带 If-None-Match，没变就回 304，很便宜），
// 拿不到网络才退回缓存。所有 fetch 一律带 cache:'no-cache' 强制绕过 HTTP 缓存。
// 代价：信号很差但没断时，开头会等一小会儿才出页面（原来是一秒开）。
var CACHE = 'cet-vocab.v3';
var ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-512.png'];

// addAll 也会走 HTTP 缓存，可能把旧 index.html 又存进来——那就白改了，所以逐个 fetch
function fresh(c, u) {
  return fetch(u, { cache: 'no-cache' }).then(function (r) { if (r && r.ok) return c.put(u, r); });
}

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return Promise.all(ASSETS.map(function (u) { return fresh(c, u); })); })
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
    fetch(e.request, { cache: 'no-cache' })
      .then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
        }
        return res;
      })
      .catch(function () {
        // 断网：退回缓存。带查询串的导航（?x=1）匹配不上原条目，兜底给首页
        return caches.match(e.request).then(function (hit) {
          return hit || caches.match('./index.html');
        });
      })
  );
});
