/* DONCHI 2.0 safe offline shell; no auth API responses or user data cached. */
const CACHE='donchi-enterprise-v2.0.0';
const SHELL=[
  '/', '/index.html', '/app/', '/platform/', '/platform/settings.html',
  '/site/','/site/style.css',
  '/style.css?v=2.0.0', '/premium.css?v=2.0.0',
  '/app.js?v=2.0.0','/v5.js?v=1.1.0','/pwa-install.js?v=2.0.0',
  '/platform-admin.js?v=1.2.0','/platform-admin.css?v=2.0.0',
  '/platform/settings.js?v=1.3.0','/icon.svg','/manifest.webmanifest'
];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE)
    .then(cache=>cache.addAll(SHELL))
    .then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(
    keys.filter(key=>key.startsWith('donchi-enterprise-')&&key!==CACHE)
      .map(key=>caches.delete(key))
  )).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const req=event.request,url=new URL(req.url);
  if(url.origin!==self.location.origin || req.method!=='GET' ||
     url.pathname.startsWith('/api/') || req.headers.has('Authorization'))return;
  // HTML and code must try the network first to avoid a stale application.
  const networkFirst=req.mode==='navigate'||/\.(js|css)$/.test(url.pathname);
  if(networkFirst){
    event.respondWith(fetch(req).catch(async()=>{
      const cached=await caches.match(req,{ignoreSearch:false});
      return cached||Response.error();
    }));
  } else if(SHELL.some(path=>new URL(path,self.location.origin).pathname===url.pathname)){
    event.respondWith(caches.match(req,{ignoreSearch:false}).then(
      cached=>cached||fetch(req)
    ));
  }
});
