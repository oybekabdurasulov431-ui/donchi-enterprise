const CACHE='donchi-enterprise-clean-v1.1.0';
const SHELL=['/','/index.html','/app/','/platform/','/site/','/site/style.css','/style.css?v=1.1.0','/app.js?v=1.1.0','/v5.js?v=1.1.0','/icon.svg','/manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const req=e.request,url=new URL(req.url);if(url.origin!==self.location.origin||req.method!=='GET'||url.pathname.startsWith('/api/'))return;
 if(req.mode==='navigate'){e.respondWith(fetch(req).catch(async()=> (await caches.match(url.pathname.startsWith('/site')?'/site/':url.pathname.startsWith('/platform')?'/platform/':'/app/'))||Response.error()));return;}
 e.respondWith(caches.match(req).then(cached=>cached||fetch(req)));
});
