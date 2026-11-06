const CACHE='donchi-enterprise-v1.2.1';
const SHELL=['/','/index.html','/app/','/platform/','/site/','/site/style.css','/style.css?v=1.1.0','/app.js?v=1.2.0','/v5.js?v=1.1.0','/platform-admin.js?v=1.2.0','/platform-admin.css?v=1.2.0','/icon.svg','/manifest.webmanifest'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const request=event.request, url=new URL(request.url);
  if(url.origin!==self.location.origin || request.method!=='GET' || url.pathname.startsWith('/api/'))return;
  const cacheFallback=async()=>{
    const cached=await caches.match(request);
    return cached||Response.error();
  };
  const needsFresh=request.mode==='navigate' || /\.(js|css)$/.test(url.pathname);
  if(needsFresh){
    event.respondWith(fetch(request).catch(cacheFallback));
  }else{
    event.respondWith(caches.match(request).then(cached=>cached||fetch(request)));
  }
});
