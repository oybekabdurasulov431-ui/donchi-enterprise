/* DONCHI 1.0 Enterprise — no CDN dependencies; offline-first POS with IndexedDB outbox */
'use strict';
const $=sel=>document.querySelector(sel);
const fmt=n=>new Intl.NumberFormat('uz-UZ',{maximumFractionDigits:2}).format(Number(n)||0);
const som=n=>fmt(n)+' so‘m';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=x=>x?new Date(x).toLocaleString('uz-UZ',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
const num=x=>Number(x)||0;
const id=()=>crypto.randomUUID();
const portal=location.pathname.startsWith('/platform')?'platform':'store';
const roleHome=()=>menuRole()==='superadmin'?'/platform/':'/app/';
function routePortal(){if(!session)return false;const right=roleHome();if(location.pathname!==right){location.replace(right);return true}return false}
function ownShift(){return (state.data?.shifts||[]).find(x=>x.status==='open'&&x.cashier_id===session?.user?.id)}
const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  cart:'<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>',
  cube:'<path d="m12 2 9 5-9 5-9-5 9-5Zm-9 5v10l9 5V12M21 7v10l-9 5"/>',
  truck:'<rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 4v4h-7M5 20h.01M19 20h.01"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/>',
  wallet:'<rect x="2" y="5" width="20" height="15" rx="2"/><path d="M2 9h20M17 15h2"/>',
  trend:'<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
  chart:'<path d="M4 19V5M4 19h16M8 16v-5M13 16V7M18 16V9"/>',
  gear:'<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/><path d="m19.4 15 .1 2-2.2 2.1-2-.7-1.5.6-.9 2h-3l-.9-2-1.6-.6-2 .7-2-2.1.6-2-1-1.7-1.9-.8v-3l1.9-.8 1-1.7-.6-2 2-2.1 2 .7 1.6-.6.9-2h3l.9 2 1.5.6 2-.7 2.2 2.1-.6 2 .8 1.7 2 .8v3l-2 .8Z"/>',
  moon:'<path d="M20.9 13.1A9 9 0 0 1 10.9 3.1 9 9 0 1 0 20.9 13.1Z"/>', sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  plus:'<path d="M12 5v14M5 12h14"/>', search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>',
  alert:'<path d="m10.3 3.3-8 14A2 2 0 0 0 4 20h16a2 2 0 0 0 1.7-2.7l-8-14a2 2 0 0 0-3.4 0ZM12 9v4M12 17h.01"/>',
  check:'<path d="m5 12 5 5L20 7"/>', receipt:'<path d="M4 2h16v20l-4-2-4 2-4-2-4 2V2Z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  download:'<path d="M12 3v13m-5-5 5 5 5-5M5 19h14"/>', refresh:'<path d="M3 11a9 9 0 0 1 15-6l2 2M20 3v4h-4M21 13a9 9 0 0 1-15 6l-2-2M4 21v-4h4"/>',
  logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>', menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  arrow:'<path d="m9 18 6-6-6-6"/>', close:'<path d="M18 6 6 18M6 6l12 12"/>',
  shield:'<path d="m12 2 9 4v6c0 5-4 9-9 10-5-1-9-5-9-10V6l9-4Z"/><path d="m8 12 3 3 5-5"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
  save:'<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2Z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/>',
  trash:'<path d="M3 6h18M8 6V4h8v2m3 0-1 15H6L5 6M10 10v7M14 10v7"/>',
  edit:'<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-5 1 1-5Z"/>',
  store:'<path d="M3 10V5h18v5l-2 3-4-3-3 3-3-3-4 3-2-3Zm2 3v8h14v-8M9 21v-6h6v6"/>',
  globe:'<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/>'};
function ico(name,size=18){return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${icons[name]||icons.grid}</svg>`}

let dbPromise=null;
function dbOpen(){if(!dbPromise){dbPromise=new Promise((resolve,reject)=>{const r=indexedDB.open('donchi-offline-clean-1.1',1);r.onupgradeneeded=()=>{r.result.createObjectStore('snapshots');r.result.createObjectStore('outbox',{keyPath:'id'})};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}return dbPromise}
async function idb(store,mode,fn){const d=await dbOpen();return new Promise((resolve,reject)=>{const t=d.transaction(store,mode),s=t.objectStore(store);let result;try{result=fn(s)}catch(e){reject(e);return}t.oncomplete=()=>resolve(result?.result);t.onerror=()=>reject(t.error)})}
const cacheGet=k=>idb('snapshots','readonly',s=>s.get(k));
const cacheSet=(k,x)=>idb('snapshots','readwrite',s=>s.put(x,k));
const queueAll=async()=>{const rows=await idb('outbox','readonly',s=>s.getAll());return (rows||[]).sort((a,b)=>a.created_at.localeCompare(b.created_at))};
const queuePut=x=>idb('outbox','readwrite',s=>s.put(x));
const queueDelete=k=>idb('outbox','readwrite',s=>s.delete(k));

let session=null;
let previousSession=null;
try{previousSession=null}catch{}
localStorage.removeItem('donchi-clean-session'); // migrate old bearer credential only once
function rememberUser(user){try{localStorage.setItem('donchi-clean-last-user',JSON.stringify(user))}catch(e){console.warn('Remembering user unavailable',e)}}
function previousUser(){try{return JSON.parse(localStorage.getItem('donchi-clean-last-user')||'null')}catch{return null}}
const state={branchId:localStorage.getItem('donchi-clean-branch')||null,data:null,stores:[],role:null,view:'dashboard',storeId:localStorage.getItem('donchi-clean-shop'),online:navigator.onLine,usingCache:false,cart:{},payMode:'cash',posCustomer:'',query:'',theme:localStorage.getItem('donchi-clean-theme')||'light',modal:null,modalData:null,logoDraft:'',mobileNav:false,pending:[],syncing:false,lastReceipt:null};
document.documentElement.dataset.theme=state.theme;
// The selected shop/branch is browser-local, but the authenticated account is
// authoritative. Never carry another account's selection into the next login.
function adoptAccountStore(user,{newLogin=false}={}){
  const nextStore=user?.store_id||null;
  if(newLogin||(state.storeId||null)!==nextStore){
    state.branchId=null;
    try{localStorage.removeItem('donchi-clean-branch')}catch(e){console.warn('Branch preference unavailable',e)}
  }
  state.storeId=nextStore;
  try{localStorage.setItem('donchi-clean-shop',nextStore||'')}catch(e){console.warn('Shop preference unavailable',e)}
}

function snapshotKey(){return `v5:${session?.user?.id||'anon'}:${state.storeId||session?.user?.store_id||''}:${state.branchId||'default'}`}
function menuRole(){return session?.user?.role||''}
function can(...roles){return roles.includes(menuRole())}
function hasData(){return !!state.data?.store}
function badge(text,cls=''){return `<span class="pill ${cls}">${esc(text)}</span>`}
function toast(msg,err=false){const d=document.createElement('div');d.className='toast'+(err?' error':'');d.textContent=msg;$('#toasts').appendChild(d);setTimeout(()=>d.remove(),5000)}
function looksNetwork(e){return e instanceof TypeError||e.name==='AbortError'||e.network}
async function request(path,{method='GET',body,storeId=state.storeId,branchId=state.branchId}={}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);
  try{
    const resp=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(session?.token?{'Authorization':'Bearer '+session.token}:{}),...(storeId?{'X-Store-ID':storeId}:{}),...(branchId?{'X-Branch-ID':branchId}:{})},body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',signal:controller.signal});
    let json;try{json=await resp.json()}catch{json={detail:`Server xatosi: HTTP ${resp.status}`}}
    if(!resp.ok){const error=new Error(typeof json.detail==='string'?json.detail:'Ma’lumotlar noto‘g‘ri');error.status=resp.status;throw error}
    state.online=true;return json;
  }finally{clearTimeout(timer)}
}
async function load(){
  if(!session)return render();
  try{
    let result;
    // An old browser tab may carry a branch from another account or an
    // ephemeral demo database that was recreated after Render woke up.
    try{
      result=await request('/bootstrap',{storeId:session.user.store_id||null});
    }catch(error){
      if(error.status!==403||!state.branchId||!session.user.store_id)throw error;
      // Only retry the read-only bootstrap; never relax mutation permissions.
      result=await request('/bootstrap',{storeId:session.user.store_id,branchId:null});
      state.branchId=null;
      try{localStorage.removeItem('donchi-clean-branch')}catch(e){console.warn('Branch preference unavailable',e)}
    }
    state.data=result.data;state.stores=result.stores||[];
    state.branchId=result.data?.branch_id||null;
    if(state.branchId){try{localStorage.setItem('donchi-clean-branch',state.branchId)}catch(e){console.warn('Branch preference unavailable',e)}}
    state.storeId=menuRole()==='superadmin'?null:(session.user.store_id||state.data?.store?.id||null);
    state.usingCache=false;
    // Browser storage can be unavailable (private mode, quota, blocked IndexedDB).
    // Do not mark a successful server response as a failed API request.
    try{await cacheSet(snapshotKey(),{data:state.data,stores:state.stores,at:Date.now()})}
    catch(cacheError){console.warn('Offline snapshot could not be saved:',cacheError)}
    try{localStorage.setItem('donchi-clean-shop',state.storeId||'')}catch(cacheError){console.warn('Shop preference not saved:',cacheError)}
  }catch(e){
    if(e.status===401){logout('Sessiya muddati tugadi. Qayta kiring.');return}
    if(!looksNetwork(e)){toast(e.message,true);return}
    state.online=false;
    const cached=await cacheGet(snapshotKey());
    if(cached){state.data=cached.data;state.stores=cached.stores;state.usingCache=true}
    else {toast('Internet yo‘q. Bu do‘kon bir marta online ochilgan bo‘lishi kerak.',true)}
  }
  try{state.pending=await queueAll()}catch(cacheError){
    state.pending=[];
    console.warn('Offline queue unavailable:',cacheError);
  }
  render();
}
function saveCache(){if(state.data)cacheSet(snapshotKey(),{data:state.data,stores:state.stores,at:Date.now()}).catch(console.error)}
function logout(msg){session=null;state.data=null;state.pending=[];localStorage.removeItem('donchi-clean-session');localStorage.removeItem('donchi-clean-last-user');localStorage.removeItem('donchi-clean-shop');state.storeId=null;state.branchId=null;render();if(msg)toast(msg,true)}
async function signOut(){
  if(!navigator.onLine){toast('To‘liq chiqish uchun serverga ulaning',true);return}
  try{await request('/logout',{method:'POST',storeId:null})}
  catch(e){if(looksNetwork(e)){toast('Serverga ulanishni tekshiring',true);return}}
  logout();
}
async function login(username,password){try{const r=await request('/login',{method:'POST',body:{username,password,totp:document.querySelector('#login-form [name=totp]')?.value||null},storeId:null});session={user:r.user};rememberUser(r.user);adoptAccountStore(r.user,{newLogin:true});state.view=menuRole()==='superadmin'?'platform':menuRole()==='seller'?'pos':menuRole()==='warehouse'?'inventory':'dashboard';state.cart={};if(routePortal())return;await load();toast('Xush kelibsiz, '+r.user.full_name)}catch(e){toast(e.message||'Ulanish xatosi',true)}}
async function switchShop(shop){if(!shop||shop===state.storeId)return;state.storeId=shop;state.branchId=null;try{localStorage.removeItem('donchi-clean-branch')}catch(e){console.warn(e)}state.cart={};state.posCustomer='';state.query='';state.view=menuRole()==='superadmin'?'platform':'dashboard';await load()}
async function mutate(path,body,{method='POST',offlineType=null}={}){
  if(!state.online && !offlineType)throw new Error('Bu amal uchun internet kerak');
  try{const r=await request(path,{method,body});await load();return {offline:false,result:r}}
  catch(e){
    if(e.status===401){
      logout('Sessiya tugagan. Qayta kiring.');
      throw new Error('Sessiya tugagan. Qayta kiring.');
    }
    if(e.status||!offlineType||!looksNetwork(e))throw e;
    state.online=false;
    const op={id:id(),store_id:state.storeId,branch_id:state.branchId,user_id:session.user.id,path,method,body,type:offlineType,status:'pending',error:'',created_at:new Date().toISOString()};
    await queuePut(op);state.pending=await queueAll();applyOptimistic(op);saveCache();render();toast('Internet yo‘q — amal offline navbatga yozildi');return {offline:true,result:{ok:true}}
  }
}
function applyOptimistic(op){const d=state.data;if(!d)return;
  if(op.type==='customer')d.customers.unshift({...op.body,created_at:new Date().toISOString()});
  if(op.type==='sale'){
    const lines=op.body.lines.map(x=>{const p=d.products.find(z=>z.id===x.product_id);if(p){p.stock=Math.max(0,p.stock-x.qty);if(d.branch_stock&&d.branch_stock[p.id]!==undefined)d.branch_stock[p.id]=Math.max(0,d.branch_stock[p.id]-x.qty)}return {...x,name:p?.name||'Mahsulot',price:p?.price||0,cost:p?.cost||0,unit:p?.unit||''}});
    const total=lines.reduce((s,x)=>s+x.qty*x.price,0),debt=Math.max(0,total-num(op.body.cash_paid)-num(op.body.card_paid));
    d.sales.unshift({id:op.id,customer_id:op.body.customer_id,customer_name:d.customers.find(c=>c.id===op.body.customer_id)?.name||'',subtotal:total,cash_paid:op.body.cash_paid,card_paid:op.body.card_paid,debt,created_at:new Date().toISOString(),lines,offline:true});
    const b=d.balances.find(x=>x.id===op.body.customer_id);if(b)b.balance+=debt;
    d.stats.revenue+=total;d.stats.today+=total;d.stats.debt+=debt;d.stats.sale_count++;
  }
  if(op.type==='payment'){
    const b=d.balances.find(x=>x.id===op.body.customer_id);if(b)b.balance-=op.body.amount;
    d.stats.debt-=op.body.amount;
    d.payments.unshift({...op.body,id:op.id,created_at:new Date().toISOString(),offline:true,customer_name:d.customers.find(x=>x.id===op.body.customer_id)?.name});
  }
}
async function syncQueue(){if(state.syncing||!session||!navigator.onLine)return;
  state.syncing=true;render();let count=0;
  try{
    const pending=await queueAll();
    for(const op of pending){
      if(op.user_id!==session.user.id||op.store_id!==state.storeId)continue;
      if(op.status==='error'){
        toast('Offline navbatda qo‘lda tekshirilishi kerak bo‘lgan amal bor. Sinxronlash oynasini oching.',true);
        break;
      }
      try{
        await request(op.path,{method:op.method,body:op.body,branchId:op.branch_id});await queueDelete(op.id);count++;
      }catch(e){
        if(looksNetwork(e)){state.online=false;break}
        if(e.status===401){toast('Sessiya tugagan. Qayta kiring.',true);break}
        op.status='error';op.error=e.message;await queuePut(op);toast('Sinxronlash to‘xtadi: '+e.message,true);break;
      }
    }
    state.pending=await queueAll();
    if(count)toast(`${count} ta offline amal serverga yuborildi`);
    if(state.online){try{const r=await request('/bootstrap');state.data=r.data;state.stores=r.stores;state.usingCache=false;await saveCache()}catch(e){console.warn(e)}}
  }finally{state.syncing=false;render()}
}
function visibleOutbox(){return state.pending.filter(op=>op.user_id===session?.user?.id&&op.store_id===state.storeId)}
async function retryOfflineOp(opId){
  const op=visibleOutbox().find(x=>x.id===opId&&x.status==='error');
  if(!op)return;
  if(!confirm('Avval serverdagi natijani va ombor qoldig‘ini tekshiring. Amalni qayta yuborishni tasdiqlaysizmi?'))return;
  op.status='pending';op.error='';await queuePut(op);
  state.pending=await queueAll();
  await syncQueue();
}
async function discardOp(opId){const op=visibleOutbox().find(x=>x.id===opId);if(!op)return;if(!confirm('Offline amalni bekor qilasizmi? Bu savdo serverga YUBORILMAYDI.'))return;await queueDelete(opId);state.pending=await queueAll();if(state.online)await load();else toast('Amal navbatdan olib tashlandi. Offline ko‘rinish qayta online bo‘lganda yangilanadi.');render()}
const menus=[
 ['platform','Super Admin','shield',['superadmin'],'PLATFORMA'],
 ['releases-admin','Yangiliklarni boshqarish','megaphone',['superadmin'],'PLATFORMA'],
 ['inquiries','Demo so‘rovlari','users',['superadmin'],'PLATFORMA'],
 ['platform-settings','Sozlamalar','gear',['superadmin'],'PLATFORMA'],
 ['dashboard','Boshqaruv paneli','grid',['owner','manager'],'ASOSIY BOSHQARUV'],
 ['pos','Sotuvchi / POS','cart',['seller','manager','owner'],'ASOSIY BOSHQARUV'],
 ['shifts','Kassa smenasi','clock',['seller','manager','owner'],'ASOSIY BOSHQARUV'],
 ['returns','Qaytarishlar','receipt',['manager','owner'],'ASOSIY BOSHQARUV'],
 ['products','Mahsulotlar','cube',['warehouse','manager','owner'],'ASOSIY BOSHQARUV'],
 ['inventory','Ombor & Kirim','truck',['warehouse','manager','owner'],'OMBOR VA SAVDO'],
 ['lots','Partiyalar va muddati','cube',['warehouse','manager','owner'],'OMBOR VA SAVDO'],
 ['branches','Filiallar va transfer','store',['warehouse','manager','owner'],'OMBOR VA SAVDO'],
 ['deliveries','Yetkazib berish','truck',['seller','manager','owner'],'OMBOR VA SAVDO'],
 ['debts','Nasiya daftari','wallet',['seller','manager','owner'],'OMBOR VA SAVDO'],
 ['customers','Mijozlar','users',['seller','manager','owner'],'OMBOR VA SAVDO'],
 ['crm','CRM va mijoz kartasi','users',['manager','owner'],'TAHLIL VA TIZIM'],
 ['finance','Moliya va ta’minotchilar','wallet',['manager','owner'],'TAHLIL VA TIZIM'],
 ['insights','Aqlli tahlilchi','chart',['manager','owner'],'TAHLIL VA TIZIM'],
 ['telegram','Telegram hisobotlari','megaphone',['owner'],'TAHLIL VA TIZIM'],
 ['updates','DONCHI yangiliklari','receipt',['seller','warehouse','manager','owner'],'TAHLIL VA TIZIM'],
 ['security','Audit va xavfsizlik','shield',['owner'],'TAHLIL VA TIZIM'],
 ['analytics','Hisobotlar','chart',['manager','owner'],'TAHLIL VA TIZIM'],
 ['team','Xodimlar','users',['owner'],'TAHLIL VA TIZIM'],
 ['settings','Sozlamalar','gear',['owner'],'TAHLIL VA TIZIM'],
 ['sync','Sinxronlash','refresh',['warehouse','seller','manager','owner'],'TAHLIL VA TIZIM']
];
function canMenu(m){const key={debts:'debts',returns:'returns',analytics:'analytics',deliveries:'delivery',finance:'finance',crm:'crm',branches:'branches',telegram:'telegram',insights:'insights'}[m[0]];return can(...m[3])&&(!key||state.data?.features?.[key]!==false)}
function navItems(){let last='';return menus.filter(canMenu).map(m=>{const section=m[4]!==last?`<div class="nav-section">${m[4]}</div>`:'';last=m[4];return section+`<button class="navlink ${state.view===m[0]?'active':''}" data-a="nav" data-v="${m[0]}">${ico(m[2])}<span>${m[1]}</span>${m[0]==='sync'&&visibleOutbox().length?badge(visibleOutbox().length,'warning'):''}</button>`}).join('')}
function head(title,subtitle,actions=''){return `<div class="page-head"><div><p class="eyebrow">DONCHI • BUSINESS SUITE</p><h1>${title}</h1><p class="subtitle">${subtitle}</p></div><div class="actions">${actions}</div></div>`}
function btn(icon,text,a,cls=''){return `<button class="btn ${cls}" data-a="${a}">${ico(icon,16)} ${text}</button>`}
function stat(label,value,sub,icon='chart',color=''){return `<div class="stat"><div class="stat-top"><span class="slabel">${label}</span><span class="stat-icon ${color}">${ico(icon)}</span></div><div class="svalue">${value}</div><small>${sub}</small></div>`}
function empty(label='Ma’lumot hozircha yo‘q',sub='Yangi ma’lumot qo‘shilganda shu yerda paydo bo‘ladi'){return `<div class="empty"><div class="empty-ico">${ico('cube',26)}</div><h4>${label}</h4><p>${sub}</p></div>`}
function table(headers,rows){return `<div class="tablewrap"><table class="table"><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')||`<tr><td colspan="${headers.length}">${empty()}</td></tr>`}</tbody></table></div>`}
function formField(name,label,type='text',value='',options={}){const attrs=`name="${name}" ${options.required?'required':''} ${options.min!==undefined?`min="${options.min}"`:''} ${options.step?`step="${options.step}"`:''}`;return `<div class="form-group"><label>${label}</label><input class="input" type="${type}" ${attrs} value="${esc(value)}" placeholder="${esc(options.placeholder||'')}"/></div>`}
function opts(arr,sel){return arr.map(([val,label])=>`<option value="${esc(val)}" ${String(val)===String(sel)?'selected':''}>${esc(label)}</option>`).join('')}
function selField(name,label,arr,selected){return `<div class="form-group"><label>${label}</label><select class="input" name="${name}">${opts(arr,selected)}</select></div>`}
function renderLogin(){return `<div class="login-wrap"><div class="login-left"><div class="login-brand"><span class="brand-mark brand-icon"><img src="/icon.svg" alt="" /></span><div>DON<span style="color:#F0BD55">CHI</span><div class="brand-sub">ENTERPRISE PLATFORM • 1.0</div></div></div><div><span class="login-tag">${ico('shield',15)} ONLINE + OFFLINE PWA</span><h1>Savdo, ombor va nasiyani bir joydan boshqaring.</h1><p>Yem do‘konlari uchun ishlab chiqilgan tezkor POS, shaffof hisobotlar va avtomatik sinxronlash bilan qulay biznes tizimi.</p></div><div style="color:#aec4cd;font-size:12px">© DONCHI 2026 · Professional boshqaruv platformasi</div></div><div class="login-form-area"><div class="brand-mark brand-icon" style="margin-bottom:30px"><img src="/icon.svg" alt="DONCHI"/></div><h2>Xush kelibsiz!</h2><p class="sub">Hisobingizga bir marta kiring. Ushbu qurilmada sessiya saqlanadi.</p><form id="login-form">${formField('username','Login','text','','').replace('type="text"','type="text" autocomplete="username" autocapitalize="none"')}${formField('password','Parol','password','','').replace('type="password"','type="password" autocomplete="current-password"')}${formField('totp','2FA kodi (yoqilgan bo‘lsa)','text','','')}<button type="submit" class="btn block" style="margin-top:13px">${ico('arrow',17)} Tizimga kirish</button></form><p class="subtitle" style="margin-top:25px">${ico('shield',16)} Har bir do‘kon ma’lumotlari alohida himoyalangan. Sessiya ushbu qurilmada 30 kun saqlanadi va foydalanilganda yangilanadi. Chiqish tugmasi sessiyani bekor qiladi.</p></div></div>`}
function shell(page){const u=session.user,s=(menuRole()==='superadmin'&&window.platformAdmin?.data?.brand?{name:window.platformAdmin.data.brand.brand_name,logo:window.platformAdmin.data.brand.logo}:state.data?.store)||{},pending=visibleOutbox();return `<div class="mobile-shade ${state.mobileNav?'open':''}" data-a="mobile-close"></div><div class="layout"><aside class="sidebar ${state.mobileNav?'open':''}"><div class="sidebar-logo"><span class="brand-mark brand-icon"><img src="/icon.svg" alt="" /></span><div><div class="brand-text">DON<span>CHI</span> <span style="font-size:10px;background:#1c655e;padding:3px 5px;border-radius:5px;color:#d9f8ed">1.0</span></div><div class="brand-sub">ENTERPRISE MANAGEMENT</div></div></div><div class="sidebar-store"><span class="store-icon">${s.logo?`<img src="${esc(s.logo)}" style="width:31px;height:31px;object-fit:contain;border-radius:8px"/>`:ico('store',20)}</span><div style="min-width:0"><div class="store-title">${esc(s.name||'DONCHI platforma')}</div><div class="store-sub">${esc(u.role)} · ${state.online?'Online':'Offline'}</div></div></div><nav class="sidebar-nav">${navItems()}</nav><div class="sidebar-foot"><div class="side-help"><strong>${ico('refresh',15)} Sinxronlash nazorati</strong>${pending.length?`${pending.length} ta amalga navbat bor`:state.online?'Ma’lumotlar server bilan ulangan':'Offline savdolar navbatda saqlanadi'}</div>DONCHI v1.0 • ${state.usingCache?'Offline snapshot':'Online server'}</div></aside><div class="main"><header class="topbar"><button class="icon-btn mobile-toggle" data-a="mobile-toggle" aria-label="Menyu">${ico('menu')}</button><div class="breadcrumbs">DONCHI <span style="margin:0 8px;color:var(--stroke)">›</span> <strong>${menus.find(m=>m[0]===state.view)?.[1]||'Boshqaruv'}</strong></div><div class="rightbar">${menuRole()!=='superadmin'&&state.stores.length>1?`<select class="storeselect" id="store-select" aria-label="Do‘konni tanlang">${opts(state.stores.filter(x=>x.status==='active').map(x=>[x.id,x.name]),state.storeId)}</select>`:''}${menuRole()!=='superadmin'&&(state.data?.branches||[]).length>1?`<select class="storeselect" id="branch-select" aria-label="Filialni tanlang">${opts(state.data.branches.map(b=>[b.id,b.name]),state.branchId)}</select>`:''}<span class="online ${state.online?'':'offline'}"><span class="dot"></span>${state.online?'Online':'Offline'}${pending.length?` · ${pending.length}`:''}</span><button class="icon-btn" data-a="theme" aria-label="Tungi yoki kunduzgi rejim">${ico(state.theme==='light'?'moon':'sun',18)}</button><button class="icon-btn" data-a="sync-now" title="Sinxronlash">${ico('refresh',18)}</button><div class="userbadge"><span class="avatar">${esc(u.full_name.slice(0,2).toUpperCase())}</span><div><b>${esc(u.full_name)}</b><span>${esc(u.role)}</span></div></div><button class="icon-btn" data-a="logout" title="Chiqish">${ico('logout',17)}</button></div></header><main class="content">${state.usingCache?`<div class="alert mb">${ico('alert',16)} Offline nusxa ko‘rsatilmoqda. Savdolar qurilmada navbatga yoziladi; serverga yuborish uchun internet va ushbu hisob kerak.</div>`:''}${page}</main></div></div>`}
function render(){const app=$('#app');if(!session){app.innerHTML=renderLogin();$('#modal-root').innerHTML='';return}
  if(!hasData()&&menuRole()!=='superadmin'){app.innerHTML=shell(`<div class="panel panelpad">${empty('Do‘kon ma’lumotlari yuklanmadi','Internet ulanishini tekshiring yoki oldin online ishlatilgan do‘konni tanlang')}<div style="text-align:center;margin-top:14px">${btn('refresh','Qayta urinish','load','secondary')}</div></div>`);return}
  const pages={platform,inquiries,'platform-settings':window.platformSettingsPage,dashboard,pos,shifts,returns:returnsPage,products,inventory,debts,customers,analytics,team,settings,sync,...v5Pages()};const view=pages[state.view]&&canMenu(menus.find(m=>m[0]===state.view))?state.view:(menuRole()==='superadmin'?'platform':menuRole()==='seller'?'pos':menuRole()==='warehouse'?'inventory':'dashboard');app.innerHTML=shell(pages[view]());renderModal();
}
function dailyPoints(){const s=state.data.sales||[];return Array.from({length:7},(_,i)=>{const d=new Date();d.setDate(d.getDate()-(6-i));const key=d.toDateString();return {label:String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0'),value:s.filter(x=>new Date(x.created_at).toDateString()===key).reduce((a,b)=>a+b.subtotal,0)}})}
function lineChart(points){const w=740,h=230,p=28,max=Math.max(1,...points.map(x=>x.value)),coords=points.map((x,i)=>[p+i*(w-2*p)/(points.length-1),h-p-x.value/max*(h-2*p)]),path=coords.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' '),area=path+` L${w-p} ${h-p} L${p} ${h-p}Z`;
  return `<svg class="chart" viewBox="0 0 ${w} ${h+35}" role="img" aria-label="Oxirgi 7 kun savdolari"><defs><linearGradient id="shaded" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1cc39c" stop-opacity=".22"/><stop offset="1" stop-color="#1cc39c" stop-opacity="0"/></linearGradient></defs>${[0,.25,.5,.75,1].map(x=>`<line x1="${p}" x2="${w-p}" y1="${p+x*(h-2*p)}" y2="${p+x*(h-2*p)}" stroke="var(--stroke)" stroke-dasharray="4 5"/>`).join('')}<path d="${area}" fill="url(#shaded)"/><path d="${path}" fill="none" stroke="#12b795" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>${coords.map((c,i)=>`<circle cx="${c[0]}" cy="${c[1]}" r="5" fill="var(--surface)" stroke="#12b795" stroke-width="3"/><text x="${c[0]}" y="${h+10}" text-anchor="middle" font-size="12" fill="var(--muted)">${esc(points[i].label)}</text>`).join('')}</svg>`}
function salesTable(items,limit=8){return table(['SAVDO','MIJOZ','SUMMA','TO‘LOV','HOLAT'],items.slice(0,limit).map(s=>`<tr><td><b>#${esc(s.id.slice(0,8).toUpperCase())}</b><small>${dt(s.created_at)}</small></td><td>${esc(s.customer_name||'Oddiy mijoz')}</td><td><b>${som(s.subtotal)}</b></td><td>${esc((s.method||'').toUpperCase()||'—')}</td><td>${s.offline?badge('Offline navbat','warning'):s.debt>0?badge('Nasiya','warning'):badge('To‘langan')}</td></tr>`))}
function dashboard(){const d=state.data,stats=d.stats||{},low=d.products.filter(x=>x.stock<=x.min_stock).sort((a,b)=>a.stock-b.stock),pays=d.balances.filter(x=>x.balance>0),sales=d.sales||[];
  return head('Xush kelibsiz! 👋',`${esc(d.store.name)} do‘koni — bugungi biznes ko‘rsatkichlari`,btn('plus','Yangi savdo','go-pos')+ (can('owner','manager')?btn('cube','Mahsulot qo‘shish','new-product','secondary'):''))+
  `<div class="stats-grid">${stat('Bugungi savdo',som(stats.today||0),'Bugungi tushum emas, jami sotuv', 'wallet')}${stat('Umumiy savdo',som(stats.revenue||0),`${stats.sale_count||0} ta savdo yozuvi`,'trend','blue')}${stat('Ombor tannarxi',som(stats.stock_value||0),`${d.products.length} turdagi mahsulot`,'cube','orange')}${stat('Qolgan nasiya',som(stats.debt||0),`${pays.length} ta qarzdor mijoz`,'wallet','red')}</div>`+
  `<div class="grid-2"><div class="panel"><div class="panel-head"><div><h3>Daromad dinamikasi</h3><p>Oxirgi 7 kunlik savdolar grafigi</p></div>${badge('7 kunlik')}</div><div class="panel-body">${lineChart(dailyPoints())}<div class="legend"><span class="dot"></span> Savdo hajmi (so‘m)</div></div></div><div class="panel"><div class="panel-head"><div><h3>Ombor ogohlantirishlari</h3><p>Kam qolgan mahsulotlar</p></div><button class="link" data-a="nav" data-v="inventory">Hammasi →</button></div><div class="panel-body">${low.length?low.slice(0,6).map(p=>`<div class="listrow"><div class="list-icon">${ico('cube')}</div><div class="rowgrow"><b>${esc(p.name)}</b><small>Minimal: ${fmt(p.min_stock)} ${esc(p.unit)}</small></div>${badge(fmt(p.stock)+' '+p.unit,'warning')}</div>`).join(''):empty('Ombor me’yorda','Kam qolgan mahsulot yo‘q')}</div></div></div>`+
  `<div class="grid-2 mt"><div class="panel"><div class="panel-head"><div><h3>So‘nggi savdolar</h3><p>Oxirgi operatsiyalar</p></div><button class="link" data-a="nav" data-v="analytics">Hisobot →</button></div>${salesTable(sales,5)}</div><div class="panel"><div class="panel-head"><div><h3>Tezkor amallar</h3><p>Ishni bir bosishda boshlang</p></div></div><div class="panel-body">${[['cart','Yangi savdo','POS orqali savdo qilish','pos'],['truck','Omborga kirim','Yangi tovar qabul qilish','inventory'],['wallet','Qarzdorlar','Nasiya daftarini ochish','debts'],['chart','Hisobotlar','Tushum va foydani ko‘rish','analytics']].filter(x=>can(...menus.find(m=>m[0]===x[3])[3])).map(x=>`<button class="listrow" style="width:100%;text-align:left;background:none;border-left:0;border-right:0;border-top:0;color:var(--text)" data-a="nav" data-v="${x[3]}"><span class="list-icon">${ico(x[0])}</span><span class="rowgrow"><b>${x[1]}</b><small>${x[2]}</small></span>${ico('arrow',16)}</button>`).join('')}</div></div></div>`}
function inquiries(){const rows=state.data?.inquiries||[];
 return head('Demo so‘rovlari','DONCHI tanishtiruv sahifasidan yuborilgan mijozlar',`<a class="btn secondary" href="/site/" target="_blank" rel="noopener">${ico('globe',16)} Tanishtiruv saytini ochish</a>`)+
 `<div class="stats-grid">${stat('Jami so‘rovlar',rows.length,'Qabul qilingan murojaatlar','users')}${stat('Yangi',rows.filter(x=>x.status==='new').length,'Aloqa kutilmoqda','alert')}${stat('Bog‘lanilgan',rows.filter(x=>x.status==='contacted').length,'Mijozga javob berilgan','check')}${stat('Yakunlangan',rows.filter(x=>x.status==='closed').length,'Yopilgan so‘rovlar','chart')}</div>`+
 `<div class="panel"><div class="panel-head"><div><h3>Mijozlar murojaatlari</h3><p>Telefon raqamlari faqat Super Admin uchun ko‘rinadi.</p></div></div>${table(['MIJOZ','BIZNES','HUDUD','TELEFON','SANA','HOLAT'],rows.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.business)}</td><td>${esc(x.city||'—')}</td><td><a href="tel:${esc(x.phone)}">${esc(x.phone)}</a></td><td>${dt(x.created_at)}</td><td><select class="storeselect" data-lead-id="${esc(x.id)}" aria-label="Murojaat holatini o‘zgartirish">${opts([['new','Yangi'],['contacted','Bog‘lanildi'],['closed','Yakunlandi']],x.status)}</select></td></tr>`))}</div>`+
 `<div class="notice-strip mt">${ico('shield',16)} Bu demo murojaatlari lokal bazada saqlanadi. Ommaviy internetga chiqarishdan oldin maxfiylik siyosati va himoya vositalarini joriy eting.</div>`;
}
function platform(){const d=state.data||{},stores=d.platform||[];const total=stores.reduce((n,x)=>n+x.revenue,0);return head('Super Admin panel', 'Barcha do‘konlar, obunalar, savdo va holatlarni boshqaring',btn('plus','Yangi do‘kon ochish','new-store'))+
  `<div class="stats-grid">${stat('Barcha do‘konlar',stores.length,'Platformadagi filiallar','store')}${stat('Faol do‘konlar',stores.filter(x=>x.status==='active').length,'Sistemadan foydalanmoqda','check')}${stat('Jami foydalanuvchilar',stores.reduce((a,b)=>a+b.users,0),'Do‘kon xodimlari','users','blue')}${stat('Jami savdolar',som(total),'Platformadagi sotuvlar','chart','orange')}</div>`+
  `<div class="panel"><div class="panel-head"><div><h3>Do‘konlar ro‘yxati</h3><p>Ma’lumotlar do‘kon bo‘yicha alohida saqlanadi</p></div></div>${table(['DO‘KON','TARIF','STATUS','XODIMLAR','SAVDOLAR','AMALLAR'],stores.map(s=>`<tr><td><b>${esc(s.name)}</b><small>ID: ${esc(s.id.slice(0,8))}</small></td><td>${badge(s.plan,'blue')}</td><td>${badge(s.status==='active'?'Faol':'To‘xtatilgan',s.status==='active'?'':'danger')}</td><td>${s.users}</td><td><b>${som(s.revenue)}</b><small>${s.sales} ta savdo</small></td><td><select class="storeselect" data-plan-id="${s.id}" aria-label="Do‘kon tarifini belgilash">${opts([['Start','Start'],['Business','Business'],['Premium','Premium'],['Enterprise','Enterprise']],s.plan)}</select> <button class="btn sm secondary" data-a="store-modules" data-id="${s.id}">${ico('gear',14)} Modullar</button> <button class="btn sm ${s.status==='active'?'secondary':'soft'}" data-a="toggle-store" data-id="${s.id}" data-status="${s.status}">${s.status==='active'?'To‘xtatish':'Faollashtirish'}</button></td></tr>`))}</div>`+
  `<div class="alert mt">${ico('alert',17)} DEMO SERVER: SQLite ma’lumotlari Render Free qayta ishga tushganda o‘chishi mumkin. Haqiqiy biznesdan oldin doimiy baza va tashqi backup talab qilinadi.</div><div class="alert mt">${ico('shield',17)} Super Admin bu yerda faqat platforma, tarif va do‘kon holatlarini boshqaradi. Do‘kon ichidagi savdolarni esa faqat do‘kon xodimlari amalga oshiradi. Tariflar hozircha ko‘rgazmali; avtomatik to‘lov tizimi ulanmagan.</div>`}
function pos(){const d=state.data,prods=d.products.filter(p=>(d.branch_stock?.[p.id]??p.stock)>0),filtered=prods.filter(p=>(p.name+' '+p.sku+' '+p.category).toLowerCase().includes(state.query.toLowerCase())),cart=Object.entries(state.cart).map(([key,qty])=>({p:d.products.find(x=>x.id===key),qty})).filter(x=>x.p),total=cart.reduce((s,x)=>s+x.p.price*x.qty,0),balance=d.balances.find(x=>x.id===state.posCustomer)?.balance||0;
  return head('Sotuvchi / POS', `Tanlangan filial: ${d.branches?.find(b=>b.id===state.branchId)?.name||'Asosiy'} · Naqd, karta va nasiya`,btn('users','Yangi mijoz','new-customer','secondary')+btn('wallet','Qarzlar','go-debts','secondary'))+
  `${ownShift()?`<div class="success-strip mb">${ico('check',17)} Kassa smenasi ochiq · savdo qilish mumkin</div>`:`<div class="notice-strip mb">${ico('alert',17)} Savdodan oldin kassa smenasini oching. <button class="btn sm secondary" data-a="nav" data-v="shifts">Smenani ochish</button></div>`}<div class="pos-grid"><section class="panel"><div class="panel-head"><div><h3>Mahsulot tanlash</h3><p>Mahsulotni bir marta bosish — savatchaga qo‘shadi</p></div>${badge(`${prods.length} mahsulot`)}</div><div class="table-tools"><div class="search">${ico('search',17)}<input id="pos-search" placeholder="Mahsulot nomi yoki SKU..." value="${esc(state.query)}" /></div></div><div class="pos-items">${filtered.length?filtered.map(p=>`<button class="product-card" data-a="cart-add" data-id="${p.id}"><div class="pico">${ico('cube',22)}</div><div class="pname">${esc(p.name)}</div><small>${esc(p.category)} · ${fmt(d.branch_stock?.[p.id]??p.stock)} ${esc(p.unit)} qoldiq</small><div class="pbottom"><b>${som(p.price)}</b><span class="pill">${ico('plus',12)}</span></div></button>`).join(''):empty('Mahsulot topilmadi','Qidiruvni o‘zgartiring')}</div></section><section class="panel cart-panel"><div class="panel-head"><div><h3>${ico('cart',20)} Savatcha</h3><p>Buyurtma va to‘lov ma’lumotlari</p></div><button class="link" data-a="cart-clear">Tozalash</button></div><div class="panel-body"><div class="cart-items">${cart.length?cart.map(x=>`<div class="cart-item"><div class="rowgrow"><b>${esc(x.p.name)}</b><small>${som(x.p.price)} / ${esc(x.p.unit)}</small></div><div class="qtyctrl"><button data-a="cart-minus" data-id="${x.p.id}">−</button><input type="number" step="0.01" min="0.01" max="${d.branch_stock?.[x.p.id]??x.p.stock}" class="qty-num" data-qty-id="${x.p.id}" value="${x.qty}" aria-label="Miqdor"/><button data-a="cart-add" data-id="${x.p.id}">+</button></div><button class="btn plain" data-a="cart-remove" data-id="${x.p.id}">${ico('trash',15)}</button></div>`).join(''):empty('Savatcha bo‘sh','Chap tomondan mahsulot qo‘shing')}</div><div class="summation"><div class="sumline"><span>Mahsulot soni</span><b>${fmt(cart.reduce((s,x)=>s+x.qty,0))}</b></div><div class="sumline total"><span>Jami</span><strong>${som(total)}</strong></div></div><div class="form-group"><label>Mijoz (nasiya uchun majburiy)</label><select class="input" id="pos-customer">${opts([['','Oddiy xaridor'],...d.customers.map(c=>[c.id,c.name+' • '+c.phone])],state.posCustomer)}</select>${state.posCustomer?`<small>Oldingi qarzi: ${som(balance)}</small>`:''}</div><div class="form-group"><label>To‘lov usuli</label><div class="paymodes">${[['cash','Naqd'],['card','Karta'],...(d.features?.debts!==false?[['debt','Nasiya'],['mixed','Aralash']]:[])].map(x=>`<button class="${state.payMode===x[0]?'selected':''}" data-a="pay-mode" data-mode="${x[0]}">${x[1]}</button>`).join('')}</div></div>${state.payMode==='mixed'?`<div class="form-grid"><div class="form-group"><label>Naqd (so‘m)</label><input class="input" id="cash-paid" type="number" min="0" step="100" value="0"></div><div class="form-group"><label>Karta (so‘m)</label><input class="input" id="card-paid" type="number" min="0" step="100" value="0"></div></div><p class="subtitle" style="margin-bottom:15px">Qolgan summa mijozga nasiya yoziladi.</p>`:''}${state.payMode==='debt'?`<div class="alert mb">${ico('wallet',16)} To‘liq summa tanlangan mijozning qarziga qo‘shiladi.</div>`:''}<button class="btn block" data-a="make-sale" ${cart.length&&ownShift()?'':'disabled'}>${ico('receipt',18)} Savdoni yakunlash · ${som(total)}</button><div style="margin-top:12px;color:var(--muted);font-size:11px;line-height:1.6">${ico('refresh',14)} Offline rejimda savdo qurilmada saqlanadi va ulanish qaytganda serverga yuboriladi.</div></div></section></div>`}
function products(){const d=state.data,rows=d.products.filter(p=>(p.name+' '+p.sku+' '+p.category).toLowerCase().includes(state.query.toLowerCase()));return head('Mahsulotlar katalogi',`${d.products.length} turdagi tovar · narxlar va qoldiqlar`,can('owner','manager')?btn('plus','Yangi mahsulot','new-product'):'')+
 `<div class="panel"><div class="table-tools"><div class="search">${ico('search',17)}<input id="product-search" placeholder="Mahsulot, SKU qidirish..." value="${esc(state.query)}" /></div>${badge(`${rows.length} mahsulot`,'blue')}</div>${table(['MAHSULOT','SKU / KATEGORIYA','SOTUV NARXI','TANNARX','QOLDIQ','HOLAT','AMALLAR'],rows.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.sku)}<small>${esc(p.category||'—')}</small></td><td><b>${som(p.price)}</b></td><td>${som(p.cost)}</td><td>${fmt(p.stock)} ${esc(p.unit)}</td><td>${p.stock<=p.min_stock?badge('Kam qolgan','warning'):badge('Yetarli')}</td><td>${can('owner','manager')?`<button class="btn sm secondary" data-a="edit-product" data-id="${p.id}">${ico('edit',14)}</button> <button class="btn sm plain" style="color:var(--red)" data-a="delete-product" data-id="${p.id}">${ico('trash',14)}</button>`:'Faqat ko‘rish'}</td></tr>`))}</div>`}
function inventory(){const d=state.data,moves=d.movements;return head('Aqlli ombor', 'Kirim-chiqim, qoldiq nazorati va inventarizatsiya',can('warehouse','manager','owner')?btn('plus','Kirim / Chiqim','new-movement'):'')+
 `<div class="stats-grid">${stat('Mahsulot turlari',d.products.length,'Faol katalog','cube')}${stat('Tannarx bo‘yicha zaxira',som(d.stats.stock_value||0),'Taxminiy ombor qiymati','wallet','blue')}${stat('Kam qolganlar',d.stats.low_stock||0,'Buyurtma uchun signal','alert','orange')}${stat('Ombor operatsiyalari',moves.length,'Oxirgi operatsiyalar','truck')}</div><div class="grid-half"><div class="panel"><div class="panel-head"><div><h3>Qoldiq ogohlantirishlari</h3><p>Minimal qoldiqdan past mahsulotlar</p></div></div><div class="panel-body">${d.products.filter(p=>p.stock<=p.min_stock).map(p=>`<div class="listrow"><span class="list-icon">${ico('alert')}</span><div class="rowgrow"><b>${esc(p.name)}</b><small>Minimal: ${fmt(p.min_stock)} ${esc(p.unit)}</small></div>${badge(fmt(p.stock)+' '+p.unit,'warning')}</div>`).join('')||empty('Hammasi yetarli','Omborda xavfli qoldiq yo‘q')}</div></div><div class="panel"><div class="panel-head"><div><h3>Kirim-chiqim jurnali</h3><p>Oxirgi harakatlar</p></div></div>${table(['MAHSULOT','MIQDOR','SABAB','SANA'],moves.slice(0,15).map(m=>`<tr><td>${esc(m.product_name)}</td><td><b style="color:${m.delta>0?'var(--accent)':'var(--red)'}">${m.delta>0?'+':''}${fmt(m.delta)}</b></td><td>${esc(m.reason)}</td><td>${dt(m.created_at)}</td></tr>`))}</div></div>`}
function debts(){const d=state.data,bal=d.balances.filter(b=>b.balance>0.001).sort((a,b)=>b.balance-a.balance),pays=d.payments;return head('Nasiya daftari', 'Qarzdorlar, qisman to‘lovlar va to‘lov tarixi',btn('plus','Qarz to‘lovini olish','new-payment')+btn('users','Mijoz qo‘shish','new-customer','secondary'))+
 `<div class="stats-grid">${stat('Qolgan qarz',som(d.stats.debt||0),'To‘lanishi kutilmoqda','wallet','red')}${stat('Qarzdor mijozlar',bal.length,'Ochiq qarzlar','users','orange')}${stat('Qarz qaytarishlar',som(pays.reduce((s,p)=>s+p.amount,0)),'Hisobga olingan to‘lovlar','check','blue')}${stat('Jami mijozlar',d.customers.length,'Mijozlar bazasi','users')}</div><div class="panel"><div class="panel-head"><div><h3>Qarzdorlar ro‘yxati</h3><p>Mijoz tanlab, qisman yoki to‘liq to‘lovni kiritish mumkin</p></div></div>${table(['MIJOZ','TELEFON','QOLGAN QARZ','AMAL'],bal.map(b=>`<tr><td><b>${esc(b.name)}</b></td><td>${esc(b.phone||'—')}</td><td><b style="color:var(--red)">${som(b.balance)}</b></td><td><button class="btn sm soft" data-a="pay-client" data-id="${b.id}">${ico('wallet',14)} To‘lov olish</button></td></tr>`))}</div><div class="panel mt"><div class="panel-head"><div><h3>Qarz to‘lovlari tarixi</h3><p>Mijozlar qaytargan mablag‘lar</p></div></div>${table(['MIJOZ','SUMMA','USUL','SANA','STATUS'],pays.slice(0,30).map(p=>`<tr><td>${esc(p.customer_name||'Mijoz')}</td><td><b>${som(p.amount)}</b></td><td>${p.method==='cash'?'Naqd':'Karta'}</td><td>${dt(p.created_at)}</td><td>${p.offline?badge('Offline','warning'):badge('Qabul qilingan')}</td></tr>`))}</div>`}
function customers(){const d=state.data;return head('Mijozlar bazasi','Telefon raqamlari, nasiya va xaridlar tarixi',btn('plus','Yangi mijoz','new-customer'))+
 `<div class="panel"><div class="panel-head"><div><h3>Doimiy mijozlar</h3><p>Qarzdorlik barcha nasiya savdolari va to‘lovlar asosida hisoblanadi</p></div></div>${table(['MIJOZ','TELEFON','MANZIL','QARZ','SANA'],d.customers.map(c=>`<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.phone||'—')}</td><td>${esc(c.address||'—')}</td><td>${som(d.balances.find(b=>b.id===c.id)?.balance||0)}</td><td>${dt(c.created_at)}</td></tr>`))}</div>`}
function analytics(){const d=state.data,stats=d.stats||{},ex=d.expenses||[],sales=d.sales||[],top=new Map();sales.forEach(s=>(s.lines||[]).forEach(l=>top.set(l.name,(top.get(l.name)||0)+l.qty)));const best=[...top].sort((a,b)=>b[1]-a[1]).slice(0,6),cost=ex.reduce((s,x)=>s+x.amount,0),max=Math.max(1,...best.map(x=>x[1]));return head('Biznes analitika','Real savdo ma’lumotlari, foyda, xarajatlar va hisobotlar',btn('download','CSV eksport','export-csv','secondary')+btn('plus','Xarajat kiritish','new-expense'))+
 `<div class="stats-grid">${stat('Jami savdo',som(stats.revenue||0),'Sotuv hajmi','chart')}${stat('Taxminiy sof natija',som(stats.profit||0),'Yalpi foyda − xarajat','trend','blue')}${stat('Xarajatlar',som(cost),'Ro‘yxatdagi xarajatlar','wallet','orange')}${stat('Nasiya qoldig‘i',som(stats.debt||0),'To‘lanmagan qarzlar','wallet','red')}</div><div class="grid-2"><div class="panel"><div class="panel-head"><div><h3>7 kunlik savdo</h3><p>Kunlar kesimida sotuv summalari</p></div></div><div class="panel-body">${lineChart(dailyPoints())}</div></div><div class="panel"><div class="panel-head"><div><h3>Eng ko‘p sotilganlar</h3><p>Miqdor bo‘yicha</p></div></div><div class="panel-body">${best.length?best.map(([name,q])=>`<div style="margin:14px 0"><div style="display:flex;justify-content:space-between;margin-bottom:7px;font-size:12px"><b>${esc(name)}</b><span>${fmt(q)}</span></div><div style="height:9px;background:var(--surface3);border-radius:9px;overflow:hidden"><div style="height:100%;width:${Math.max(5,q/max*100)}%;border-radius:9px;background:linear-gradient(90deg,#14b897,#47dfbc)"></div></div></div>`).join(''):empty('Hali savdo yo‘q')}</div></div></div><div class="panel mt"><div class="panel-head"><div><h3>Xarajatlar daftari</h3><p>Xarajatlar foydadan chegiriladi</p></div></div>${table(['KATEGORIYA','IZOH','SUMMA','SANA'],ex.map(e=>`<tr><td><b>${esc(e.category)}</b></td><td>${esc(e.note)}</td><td>${som(e.amount)}</td><td>${dt(e.created_at)}</td></tr>`))}</div><div class="alert mt">${ico('alert',16)} Hisobotda sotuvlar jadvalining oxirgi 250 yozuvi hisoblanadi. Bu MVP versiyada rasmiy buxgalteriya hisobi yoki soliq hisoboti emas. Barcha davrlar hisobotini alohida server so‘rovi bilan kengaytirish kerak.</div>`}
function team(){const users=state.data.users||[];return head('Xodimlar va ruxsatlar', 'Har bir rolga alohida boshqaruv huquqlari',btn('plus','Xodim qo‘shish','new-user'))+
 `<div class="panel"><div class="panel-head"><div><h3>Jamoa</h3><p>Super Admin, egasi, menejer, sotuvchi va omborchi</p></div></div>${table(['XODIM','LOGIN','ROL','STATUS','SANA','AMAL'],users.map(u=>`<tr><td><b>${esc(u.full_name)}</b></td><td>${esc(u.username)}</td><td>${badge(u.role,'blue')}</td><td>${badge(u.active?'Faol':'Nofaol',u.active?'':'danger')}</td><td>${dt(u.created_at)}</td><td>${u.id===session.user.id?'—':`<button class="btn sm secondary" data-a="user-status" data-id="${u.id}" data-status="${u.active}">${u.active?'Bloklash':'Faollashtirish'}</button>`}</td></tr>`))}</div><div class="alert mt">${ico('shield',16)} Yangi xodimlar kuchli parol bilan yaratiladi. Har bir amal serverda rol asosida tekshiriladi.</div>`}
function settings(){const s=state.data.store;return head('Do‘kon sozlamalari','Brend, logotip, manzil, parol va interfeys',btn('save','Saqlash','save-settings'))+
 `<div class="grid-half"><div class="panel panelpad"><h3 style="margin-top:0">Brend ma’lumotlari</h3><form id="settings-form"><div class="form-group"><label>Do‘kon logotipi</label><div class="uploadbox"><img class="logo-preview" id="logo-preview" src="${esc(state.logoDraft||s.logo||'/icon.svg')}" alt="Logotip"/><input id="logo-input" type="file" accept="image/png,image/jpeg,image/webp"/><small>PNG, JPG yoki WEBP · avtomatik kichraytiriladi</small></div></div>${formField('name','Do‘kon nomi','text',s.name,{required:true})}${formField('phone','Telefon','tel',s.phone)}${formField('address','Manzil','text',s.address)}<button type="submit" class="btn">${ico('save',16)} Sozlamalarni saqlash</button></form></div><div><div class="panel panelpad"><h3 style="margin-top:0">Interfeys</h3><div class="listrow"><span class="list-icon">${ico(state.theme==='light'?'moon':'sun')}</span><div class="rowgrow"><b>Tungi / kunduzgi rejim</b><small>Tanlov qurilmada saqlanadi</small></div><button class="btn sm secondary" data-a="theme">Almashtirish</button></div><div class="listrow"><span class="list-icon">${ico('globe')}</span><div class="rowgrow"><b>Ishlash rejimi</b><small>${state.online?'Internetga ulangan':'Offline rejim'}</small></div>${badge(state.online?'Online':'Offline',state.online?'':'warning')}</div><div class="listrow"><span class="list-icon">${ico('refresh')}</span><div class="rowgrow"><b>Sinxronlash navbati</b><small>${visibleOutbox().length} ta operatsiya</small></div><button class="btn sm secondary" data-a="nav" data-v="sync">Ochish</button></div></div><div class="panel panelpad mt"><h3 style="margin-top:0">Zaxira nusxa</h3><p class="subtitle" style="margin:12px 0">Do‘kon ma’lumotlarini JSON formatida to‘liq eksport qiling (faqat online).</p><button class="btn secondary" data-a="download-backup">${ico('download',16)} JSON backup</button></div><div class="panel panelpad mt"><h3 style="margin-top:0">Xavfsizlik</h3><p class="subtitle" style="margin:12px 0">Xavfsizlik uchun parolingizni muntazam yangilang.</p><button class="btn secondary" data-a="change-password">${ico('shield',16)} Parolni o‘zgartirish</button></div></div></div>`}
function sync(){const q=visibleOutbox();return head('Online / Offline sinxronlash','Offline savdolarni xavfsiz saqlash va serverga yuborish',btn('refresh','Hozir sinxronlash','sync-now'))+
 `<div class="sync-status"><div class="panel"><small>Joriy holat</small><b>${state.online?'Online':'Offline'}</b>${badge(state.online?'Server bilan ulangan':'Aloqa yo‘q',state.online?'':'warning')}</div><div class="panel"><small>Navbatda</small><b>${q.length}</b>${badge('Qurilmada saqlanmoqda','blue')}</div><div class="panel"><small>Muammoli</small><b>${q.filter(x=>x.status==='error').length}</b>${badge('Qo‘lda ko‘rib chiqish','warning')}</div></div><div class="panel"><div class="panel-head"><div><h3>Sinxronlash navbati</h3><p>Operatsiyalar yaratilgan tartibda yuboriladi. Ombor qoldig‘i yetmasa sinxronlash to‘xtaydi.</p></div></div>${q.length?q.map(op=>`<div class="outbox-item"><span class="list-icon">${ico(op.type==='sale'?'cart':op.type==='payment'?'wallet':'users')}</span><div class="rowgrow"><b>${esc(op.type==='sale'?'Offline POS savdo':op.type==='payment'?'Qarz to‘lovi':'Mijoz qo‘shish')}</b><small>${dt(op.created_at)} · ${esc(op.id.slice(0,8))}</small>${op.error?`<p>${esc(op.error)}</p>`:''}</div>${badge(op.status==='error'?'Xato':'Navbatda',op.status==='error'?'danger':'warning')}${op.status==='error'?'<button class="btn sm secondary" data-a="retry-op" data-id="'+esc(op.id)+'">Tekshirib qayta yuborish</button>':''}<button class="btn sm secondary" data-a="discard" data-id="${op.id}">${ico('trash',14)} Bekor qilish</button></div>`).join(''):empty('Navbat bo‘sh','Offline amalga oshirilgan savdolar bu yerda chiqadi')}</div><div class="alert mt">${ico('shield',17)} Offline ishlashi uchun ilova avval internet orqali ochilib, login bajarilgan bo‘lishi kerak. Savdo mijozning shu qurilmasida vaqtincha saqlanadi. Muammo bo‘lsa operatsiyani serverga bir necha marta qo‘shmaydi — identifikatorlar nazorati ishlaydi.</div>`}
function shifts(){const d=state.data,records=d.shifts||[],current=ownShift();const history=records.slice(0,30);
 return head('Kassa smenalari','Har bir kassirning smenasi, ochilish puli va naqd farqlarni kuzatish',current?btn('clock','Smenani yopish','close-shift'):btn('plus','Smenani ochish','open-shift'))+
 `<div class="stats-grid">${stat('Smena holati',current?'Ochiq':'Yopiq',current?dt(current.opened_at):'Yangi smena oching','clock')}${stat('Kutilayotgan naqd',som(current?.expected_live||0),'Boshlang‘ich pul + naqd tushum − qaytim','wallet','blue')}${stat('Joriy savdolar',String(current?.sale_count||0),'Smena ichidagi savdolar','cart')}${stat('Jami smenalar',records.length,'Tarixda ko‘rsatilgan yozuvlar','chart','orange')}</div>`+
 `<div class="panel"><div class="panel-head"><div><h3>Kassa smenalari tarixi</h3><p>Yopilganda kutilgan va sanalgan summalar solishtiriladi</p></div></div>${table(['XODIM','OCHILDI','STATUS','KUTILGAN','SANALGAN','FARQ'],history.map(sh=>`<tr><td><b>${esc(sh.cashier_name)}</b></td><td>${dt(sh.opened_at)}</td><td>${badge(sh.status==='open'?'Ochiq':'Yopilgan',sh.status==='open'?'':'blue')}</td><td>${som(sh.status==='open'?sh.expected_live:sh.expected_cash)}</td><td>${sh.status==='open'?'—':som(sh.closing_cash)}</td><td>${sh.status==='open'?'—':badge(som(sh.variance),Math.abs(sh.variance)<.01?'':'warning')}</td></tr>`))}</div><div class="alert mt">${ico('shield',16)} Smenalar xodim bo‘yicha hisoblanadi. Serverga uzatilmagan offline operatsiyalar kutilayotgan summaga kirmaydi; yopishdan avval navbatni sinxronlang.</div>`}
function returnsPage(){const d=state.data,recs=d.returns||[],sales=(d.sales||[]).slice(0,50),open=ownShift();return head('Savdolarni qaytarish','Qaytarilgan mahsulot omborga qaytadi, to‘lov va nasiya hisoblari yangilanadi',btn('refresh','Yangilash','load','secondary'))+
 `${open?'':`<div class="notice-strip mb">${ico('alert',17)} Qaytarishni rasmiylashtirishdan oldin o‘z kassa smenangizni oching. <button class="btn sm secondary" data-a="nav" data-v="shifts">Smena</button></div>`}<div class="stats-grid">${stat('Qaytarilgan summa',som(d.stats.returned_total||0),'Barcha qaytarishlar','wallet','orange')}${stat('Qaytarish amallari',recs.length,'Oxirgi qaytarishlar','receipt')}${stat('Savdolar',d.stats.sale_count||0,'Umumiy savdo yozuvlari','cart')}</div><div class="panel"><div class="panel-head"><div><h3>Qaytarish uchun savdo tanlang</h3><p>Avval savdoni toping, keyin qaysi mahsulot va miqdorni qaytarishni ko‘rsating</p></div></div>${table(['SANA','MIJOZ','SUMMA','TO‘LOV','AMAL'],sales.map(x=>`<tr><td>${dt(x.created_at)}</td><td>${esc(x.customer_name||'Oddiy xaridor')}</td><td><b>${som(x.subtotal)}</b></td><td>${badge(x.method==='debt'?'Nasiya':x.method==='mixed'?'Aralash':x.method==='card'?'Karta':'Naqd','blue')}</td><td><button class="btn sm secondary" ${open?'':'disabled'} data-a="return-sale" data-id="${x.id}">${ico('refresh',14)} Qaytarish</button></td></tr>`))}</div><div class="panel mt"><div class="panel-head"><div><h3>Qaytarish tarixi</h3><p>Naqd qaytim, karta qaytimi va nasiya kamayishi</p></div></div>${table(['SANA','MIJOZ','QAYTARILDI','NASIYA KAMAYDI','NAQD / KARTA'],recs.map(r=>`<tr><td>${dt(r.created_at)}</td><td>${esc(r.customer_name||'Oddiy xaridor')}</td><td><b>${som(r.total)}</b></td><td>${som(r.credit_reduction)}</td><td>${som(r.refund_cash)} / ${som(r.refund_card)}</td></tr>`))}</div><div class="alert mt">${ico('alert',16)} Bu MVP’da nasiya qaytarishlari mijozning umumiy qarz qoldig‘i bo‘yicha hisoblanadi. Pulni qaytarishdan oldin haqiqiy kassani tekshiring.</div>`}
function openModal(type,data=null){state.modal=type;state.modalData=data;state.logoDraft='';renderModal()}
function closeModal(){state.modal=null;state.modalData=null;$('#modal-root').innerHTML=''}
function modalShell(title,body,wide=false){return `<div class="modal-overlay" data-a="modal-overlay"><div class="modal ${wide?'wide':''}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h3>${title}</h3><button class="x" data-a="close-modal" aria-label="Yopish">×</button></div><div class="modal-content">${body}</div></div></div>`}
function modalForm(inner,submit='Saqlash'){return `<form id="modal-form">${inner}<div class="modal-foot"><button type="button" class="btn secondary" data-a="close-modal">Bekor qilish</button><button type="submit" class="btn">${ico('save',16)} ${submit}</button></div></form>`}
function renderModal(){if(!state.modal){$('#modal-root').innerHTML='';return} if(v5ModalTypes.includes(state.modal)){renderV5Modal();return}
 let title='',body='',wide=false;const d=state.data,record=state.modalData;
 switch(state.modal){
 case 'new-product': case 'edit-product':{
   const p=state.modal==='edit-product'?d.products.find(x=>x.id===record):null;
   title=p?'Mahsulotni tahrirlash':'Yangi mahsulot qo‘shish';
   body=modalForm(`<div class="form-grid">${formField('name','Mahsulot nomi','text',p?.name||'',{required:true})}${formField('sku','SKU / kod','text',p?.sku||'',{required:true})}${formField('category','Kategoriya','text',p?.category||'')}${selField('unit','O‘lchov birligi',[['qop','Qop'],['kg','Kilogramm'],['tonna','Tonna'],['dona','Dona']],p?.unit||'qop')}${formField('price','Sotuv narxi (so‘m)','number',p?.price||0,{min:0,step:'any',required:true})}${formField('cost','Xarid narxi (so‘m)','number',p?.cost||0,{min:0,step:'any',required:true})}${!p?formField('stock','Boshlang‘ich qoldiq','number',0,{min:0,step:'any'}):''}${formField('min_stock','Minimal qoldiq','number',p?.min_stock||0,{min:0,step:'any'})}</div>${p?'<p class="subtitle" style="margin-top:15px">Qoldiqni o‘zgartirish uchun Ombor → Kirim/Chiqim bo‘limidan foydalaning.</p>':''}`,p?'Yangilash':'Mahsulot qo‘shish');wide=true;break}
 case 'new-customer':title='Yangi mijoz';body=modalForm(`${formField('name','Ism-familiya','text','',{required:true})}${formField('phone','Telefon raqami','tel','','')}${formField('address','Manzil','text','','')}`,'Mijoz qo‘shish');break;
 case 'new-payment':{
   title='Qarz to‘lovini qabul qilish';const bal=d.balances.filter(x=>x.balance>0.001),selected=record||bal[0]?.id;
   body=modalForm(`${selField('customer_id','Qarzdor mijoz',bal.map(b=>[b.id,b.name+' — '+som(b.balance)]),selected)}${formField('amount','To‘lov summasi (so‘m)','number',0,{min:1,step:'any',required:true})}${selField('method','To‘lov usuli',[['cash','Naqd'],['card','Karta']],'cash')}<div class="hint">Qarz qoldig‘idan katta to‘lov kiritilmaydi. To‘lov nasiya balansidan ayriladi.</div>`,'To‘lovni qabul qilish');break}
 case 'new-movement':title='Omborga kirim / chiqim';body=modalForm(`${selField('product_id','Mahsulotni tanlang',d.products.map(p=>[p.id,p.name+' (qoldiq: '+fmt(p.stock)+' '+p.unit+')']),d.products[0]?.id)}${formField('delta','Miqdor (+ kirim, − chiqim)','number',1,{step:'any',required:true})}${selField('reason','Operatsiya sababi',[['kirim','Ta’minotchidan kirim'],['inventar','Inventarizatsiya'],['yoqotish','Yo‘qotish / Brak'],['tuzatish','Qo‘lda tuzatish']],'kirim')}${formField('note','Izoh','text','','')}`,'Omborni yangilash');break;
 case 'new-expense':title='Yangi xarajat';body=modalForm(`${formField('category','Kategoriya','text','Transport',{required:true})}${formField('amount','Summa','number',0,{min:1,step:'any',required:true})}${formField('note','Izoh','text','','')}`,'Xarajat qo‘shish');break;
 case 'new-user':title='Yangi xodim';body=modalForm(`${formField('full_name','Ism-familiya','text','',{required:true})}${formField('username','Login (lotincha)','text','',{required:true})}${selField('role','Rol',[['seller','Sotuvchi'],['warehouse','Omborchi'],['manager','Menejer'],['owner','Do‘kon egasi']],'seller')}${formField('password','Parol (kamida 10 belgi)','password','',{required:true})}`,'Xodim yaratish');break;
 case 'new-store':title='Platformaga yangi do‘kon';body=modalForm(`${formField('name','Do‘kon nomi','text','',{required:true})}${formField('owner_name','Egasi','text','',{required:true})}${formField('username','Egasi uchun login','text','',{required:true})}${formField('password','Parol (kamida 10 belgi)','password','',{required:true})}${selField('plan','Tarif',[['Start','Start'],['Business','Business'],['Premium','Premium']],'Business')}`,'Do‘kon yaratish');break;
 case 'store-modules':{
   const shop=d.platform?.find(x=>x.id===record);if(!shop)return;
   title='Modullar — '+shop.name;
   body=modalForm(`<p class="subtitle" style="margin-bottom:20px">Oldindan ishlab chiqilib, serverga joylangan modullarni shu do‘konda yoqish yoki o‘chirish mumkin. Yangi modul kodini bu yerda avtomatik yaratib bo‘lmaydi.</p>${[['debts','Nasiya daftari','POS va qarzlar'],['returns','Qaytarishlar','Omborga qaytish'],['analytics','Biznes analitika','Savdo hisobotlari'],['delivery','Yetkazish','Buyurtma yetkazish'],['finance','Moliya','Ta’minotchi qarzlari'],['crm','CRM','Mijoz limitlari'],['branches','Filiallar','Ombor transferlari'],['telegram','Telegram','Hisobot yuborish'],['insights','Aqlli tahlil','Mahalliy tavsiyalar']].map(([key,title,desc])=>`<label class="feature-toggle"><span><b>${title}</b><small>${desc}</small></span><input type="checkbox" name="${key}" ${shop.features?.[key]!==false?'checked':''}/></label>`).join('')}`,'Modullarni saqlash');break}
 case 'open-shift':title='Kassa smenasini ochish';body=modalForm(`${formField('opening_cash','Boshlang‘ich kassa puli','number',0,{min:0,step:'any',required:true})}<div class="hint">Smena davomida naqd savdolar va naqd qarz to‘lovlari kassa hisobiga qo‘shiladi.</div>`,'Smenani ochish');break;
 case 'close-shift':{const sh=ownShift();title='Kassa smenasini yopish';body=modalForm(`<div class="notice-strip mb">Kutilayotgan naqd summa: <b>${som(sh?.expected_live||0)}</b></div>${formField('counted_cash','Kassada sanalgan naqd pul','number',sh?.expected_live||0,{min:0,step:'any',required:true})}${formField('note','Izoh','text','','')}`,'Smenani yopish');break}
 case 'return-sale':{
   const sale=d.sales.find(z=>z.id===record);if(!sale)return;
   title='Savdodan mahsulot qaytarish';
   const rows=(sale.lines||[]).map(l=>{const returned=(d.returns||[]).flatMap(r=>r.items||[]).filter(i=>i.sale_item_id===l.id).reduce((n,i)=>n+i.qty,0);const remaining=Math.max(0,l.qty-returned);return `<div class="return-line"><div><b>${esc(l.name)}</b><small>Sotilgan ${fmt(l.qty)} ${esc(l.unit)} · Qaytarish mumkin ${fmt(remaining)}</small></div><label>Qaytariladigan miqdor<input type="number" class="input" name="qty_${esc(l.id)}" min="0" max="${remaining}" step="any" value="0" /></label></div>`}).join('');
   body=modalForm(`<div class="notice-strip mb">Savdo: ${som(sale.subtotal)} · ${dt(sale.created_at)}</div>${rows}${selField('refund_method','Qaytim usuli',[['cash','Naqd'],['card','Karta']],'cash')}<div class="hint">Qarzdorlik bo‘lsa, dastur mavjud qarzning mumkin bo‘lgan qismini kamaytiradi; ortiqcha summa tanlangan usulda qaytariladi. Faqat admin yoki menejer.</div>`,'Qaytarishni tasdiqlash');wide=true;break}
 case 'change-password':title='Parolni o‘zgartirish';body=modalForm(`${formField('old_password','Eski parol','password','',{required:true})}${formField('new_password','Yangi parol (kamida 10 belgi)','password','',{required:true})}`,'Parolni yangilash');break;
 case 'receipt':{
   const sale=record;title='Savdo yakunlandi';body=`<div style="text-align:center;padding:15px 0 25px"><div class="brand-mark" style="margin:auto">${ico('check',27)}</div><h2 style="margin:12px 0 6px">${sale.offline?'Offline savdo saqlandi':'Savdo muvaffaqiyatli!'}</h2><p class="subtitle">${sale.offline?'Internet qaytganda serverga yuboriladi':'Ma’lumotlar va ombor qoldig‘i yangilandi'}</p><h1 style="font-size:32px">${som(sale.total)}</h1>${sale.debt>0?badge('Nasiya: '+som(sale.debt),'warning'):badge('To‘langan')}</div><div class="modal-foot"><button class="btn secondary" data-a="close-modal">Yopish</button><button class="btn" data-a="print-receipt">${ico('receipt',17)} Chekni chiqarish</button></div>`;break}
 default:return;
 }
 $('#modal-root').innerHTML=modalShell(title,body,wide);
}
async function onModalSubmit(form){const x=Object.fromEntries(new FormData(form).entries());try{
  if(v5ModalTypes.includes(state.modal)){await submitV5Modal(x);closeModal();return}
  switch(state.modal){
    case 'new-product':case 'edit-product':{
      for(const key of ['price','cost','stock','min_stock'])x[key]=num(x[key]);
      const updating=state.modal==='edit-product';await mutate(updating?'/products/'+state.modalData:'/products',x,{method:updating?'PUT':'POST'});toast(updating?'Mahsulot yangilandi':'Mahsulot qo‘shildi');break}
    case 'new-customer':{
      x.id=id();await mutate('/customers',x,{offlineType:'customer'});toast('Mijoz saqlandi');break}
    case 'new-payment':{
      x.amount=num(x.amount);if(x.amount<=0)throw new Error('Musbat summa kiriting');
      const bal=state.data.balances.find(b=>b.id===x.customer_id);if(!bal||x.amount>bal.balance+0.01)throw new Error('Mijoz qarzi yetarli emas');
      x.client_id=id();await mutate('/debts/pay',x,{offlineType:'payment'});toast('Qarz to‘lovi yozildi');break}
    case 'new-movement':x.delta=Number(x.delta);await mutate('/inventory/adjust',x);toast('Ombor yangilandi');break;
    case 'new-expense':x.amount=num(x.amount);await mutate('/expenses',x);toast('Xarajat qo‘shildi');break;
    case 'new-user':await mutate('/users',x);toast('Xodim qo‘shildi');break;
    case 'new-store':await mutate('/stores',x);toast('Yangi do‘kon yaratildi');break;
    case 'store-modules':{
       const modules=Object.fromEntries(['debts','returns','analytics','delivery','finance','crm','branches','telegram','insights'].map(module=>[module,!!x[module]]));
       await request('/stores/'+state.modalData+'/modules',{method:'PUT',body:{modules}});
       await load();toast('Barcha modul ruxsatlari birgalikda saqlandi');break}

    case 'open-shift':await mutate('/shifts/open',{opening_cash:num(x.opening_cash)});toast('Kassa smenasi ochildi');break;
    case 'close-shift':{const r=await mutate('/shifts/close',{counted_cash:num(x.counted_cash),note:x.note||''});toast('Smena yopildi. Farq: '+som(r.result.variance));break}
    case 'return-sale':{
      const sale=state.data.sales.find(z=>z.id===state.modalData);
      const lines=(sale?.lines||[]).map(l=>({sale_item_id:l.id,qty:Number(x['qty_'+l.id]||0)})).filter(l=>l.qty>0);
      if(!lines.length)throw new Error('Qaytariladigan miqdorni kiriting');
      const r=await mutate('/sales/'+state.modalData+'/return',{client_id:id(),items:lines,refund_method:x.refund_method||'cash'});
      toast('Qaytarish amalga oshdi: '+som(r.result.total));break}

    case 'change-password':await mutate('/account/password',x);logout('Parol o‘zgardi. Xavfsizlik uchun qayta kiring.');break;
  }
  closeModal();
 }catch(e){toast(e.message||'Xatolik',true)}
}
async function makeSale(){if(!ownShift())return toast('Avval kassa smenasini oching',true);const cart=Object.entries(state.cart).filter(([p,q])=>q>0);if(!cart.length)return toast('Savatcha bo‘sh',true);
  const total=cart.reduce((s,[pid,qty])=>s+num(state.data.products.find(p=>p.id===pid)?.price)*qty,0);
  let cash=state.payMode==='cash'?total:0,card=state.payMode==='card'?total:0;
  if(state.payMode==='mixed'){cash=num($('#cash-paid')?.value);card=num($('#card-paid')?.value)}
  if(cash<0||card<0||cash+card>total+.01)return toast('To‘lov summasi noto‘g‘ri',true);
  const debt=Math.max(0,total-cash-card);if(debt>.01&&state.data.features?.debts===false)return toast('Nasiya moduli ushbu do‘konda o‘chirilgan',true);if(debt>.01&&!state.posCustomer)return toast('Nasiya uchun mijozni tanlang',true);
  const saleItems=cart.map(([product_id,qty])=>{
    const item=state.data.products.find(p=>p.id===product_id);
    return {product_id,qty,unit_price:item.price,name:item.name};
  });
  const payload={client_id:id(),lines:saleItems.map(({product_id,qty,unit_price})=>({product_id,qty,unit_price})),cash_paid:cash,card_paid:card,customer_id:state.posCustomer||null};
  try{const r=await mutate('/sales',payload,{offlineType:'sale'});state.lastReceipt={total,debt,payload,items:saleItems,offline:r.offline,at:new Date().toISOString(),storeName:state.data.store.name};state.cart={};state.payMode='cash';state.posCustomer='';openModal('receipt',state.lastReceipt)}catch(e){toast(e.message||'Savdo amalga oshmadi',true)}
}
function printReceipt(){const receipt=state.lastReceipt;if(!receipt)return;const w=window.open('','_blank','width=420,height=650');if(!w){toast('Brauzer chek oynasini blokladi',true);return}
 const items=(receipt.items||receipt.payload.lines).map(i=>{const p=state.data?.products?.find(x=>x.id===i.product_id);return `<tr><td>${esc(i.name||p?.name||'Mahsulot')}</td><td>${fmt(i.qty)}</td><td>${som(i.qty*(i.unit_price??p?.price??0))}</td></tr>`}).join('');w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>DONCHI chek</title><style>body{font-family:Arial,sans-serif;padding:20px;max-width:360px;margin:auto;color:#222}h2{text-align:center}table{width:100%;font-size:12px;border-collapse:collapse}td{padding:8px 3px;border-bottom:1px dashed #aaa}td:last-child{text-align:right}footer{text-align:center;margin-top:25px}strong{font-size:21px}</style></head><body><h2>${esc(receipt.storeName)}</h2><p>DONCHI • ${dt(receipt.at)}</p><hr><table>${items}</table><p>Jami: <strong>${som(receipt.total)}</strong></p><p>Nasiya: ${som(receipt.debt)}</p>${receipt.offline?'<b>OFFLINE — sinxronlash kutilmoqda</b>':''}<footer>Xaridingiz uchun rahmat!</footer></body></html>`);w.document.close();w.focus();setTimeout(()=>w.print(),400)}
function csvExport(){const rows=[['ID','Sana','Mijoz','Jami','Naqd','Karta','Nasiya'],...(state.data.sales||[]).map(x=>[x.id,x.created_at,x.customer_name||'',x.subtotal,x.cash_paid,x.card_paid,x.debt])];const csv='\uFEFF'+rows.map(r=>r.map(x=>'"'+String(x??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='DONCHI-savdolar-'+new Date().toISOString().slice(0,10)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}
async function logoChange(file){if(!file)return;if(file.size>8e6){toast('Logo hajmi juda katta',true);return}if(!['image/png','image/jpeg','image/webp'].includes(file.type)){toast('Faqat PNG/JPG/WEBP',true);return}
 const url=URL.createObjectURL(file);const img=new Image();img.onload=()=>{const c=document.createElement('canvas');const ratio=Math.min(1,240/Math.max(img.width,img.height));c.width=Math.max(1,Math.round(img.width*ratio));c.height=Math.max(1,Math.round(img.height*ratio));c.getContext('2d').drawImage(img,0,0,c.width,c.height);state.logoDraft=c.toDataURL('image/webp',.7);$('#logo-preview').src=state.logoDraft;URL.revokeObjectURL(url)};img.onerror=()=>{URL.revokeObjectURL(url);toast('Rasm ochilmadi',true)};img.src=url}
async function settingsSave(form){const v=Object.fromEntries(new FormData(form).entries());v.logo=state.logoDraft||state.data.store.logo||'';try{await mutate('/settings',v,{method:'PUT'});state.logoDraft='';toast('Sozlamalar saqlandi')}catch(e){toast(e.message||'Xatolik',true)}}

async function doAction(el){const a=el.dataset.a,mid=el.dataset.id;
 try{
  if(await v5Action(el,a,mid))return;
  if(a==='mobile-toggle'||a==='mobile-close'){state.mobileNav=a==='mobile-toggle'?!state.mobileNav:false;render();return}
  if(a.startsWith('pa-')){await window.platformSettingsAction(el);return}
  if(a==='nav'){state.view=el.dataset.v;state.query='';state.mobileNav=false;render();if(state.view==='platform-settings')await window.platformSettingsLoad();window.scrollTo({top:0,behavior:'smooth'});return}
  if(a==='theme'){state.theme=state.theme==='light'?'dark':'light';localStorage.setItem('donchi-clean-theme',state.theme);document.documentElement.dataset.theme=state.theme;render();return}
  if(a==='logout'){await signOut();return}
  if(a==='close-modal'||a==='modal-overlay'){closeModal();return}
  if(a==='sync-now'){if(!navigator.onLine)return toast('Internet ulanishi yo‘q',true);await syncQueue();return}
  if(a==='load'){await load();return}
  if(a==='go-pos'){state.view='pos';render();return}
  if(a==='go-debts'){state.view='debts';render();return}
  if(a==='switch-store')return;
  if(a==='toggle-store'){const next=el.dataset.status==='active'?'paused':'active';if(!confirm('Do‘kon holatini o‘zgartirasizmi?'))return;await mutate('/stores/'+mid+'/status',{status:next});toast('Do‘kon holati o‘zgardi');return}
  if(a==='close-shift'&&visibleOutbox().length)return toast('Smenani yopishdan avval offline navbatni sinxronlang',true);
  if(['new-product','new-customer','new-payment','new-movement','new-expense','new-user','new-store','change-password','open-shift','close-shift'].includes(a)){openModal(a);return}
  if(a==='store-modules'){openModal('store-modules',mid);return}
  if(a==='return-sale'){openModal('return-sale',mid);return}
  if(a==='edit-product'){openModal(a,mid);return}
  if(a==='pay-client'){openModal('new-payment',mid);return}
  if(a==='user-status'){const active=el.dataset.status!=='1';if(!confirm('Xodim holatini o‘zgartirasizmi?'))return;await mutate('/users/'+mid+'/status',{active});toast('Xodim holati yangilandi');return}
  if(a==='delete-product'){if(!confirm('Mahsulotni o‘chirasizmi? Savdo tarixi saqlanadi.'))return;await mutate('/products/'+mid,undefined,{method:'DELETE'});toast('Mahsulot o‘chirildi');return}
  if(a==='cart-add'){const p=state.data.products.find(x=>x.id===mid);if(!p||num(state.cart[mid])+1>(state.data.branch_stock?.[mid]??p.stock))return toast('Mahsulot qoldig‘i yetarli emas',true);state.cart[mid]=num(state.cart[mid])+1;render();return}
  if(a==='cart-minus'){state.cart[mid]=Math.max(0,num(state.cart[mid])-1);if(!state.cart[mid])delete state.cart[mid];render();return}
  if(a==='cart-remove'){delete state.cart[mid];render();return}
  if(a==='cart-clear'){state.cart={};render();return}
  if(a==='pay-mode'){state.payMode=el.dataset.mode;render();return}
  if(a==='make-sale'){await makeSale();return}
  if(a==='print-receipt'){printReceipt();return}
  if(a==='export-csv'){csvExport();return}
  if(a==='download-backup'){
    const backup=await request('/export');const file=new Blob([JSON.stringify(backup,null,2)],{type:'application/json'});
    const href=URL.createObjectURL(file),download=document.createElement('a');download.href=href;download.download='DONCHI-backup-'+new Date().toISOString().slice(0,10)+'.json';download.click();setTimeout(()=>URL.revokeObjectURL(href),2000);toast('Zaxira nusxa tayyor');return
  }
  if(a==='save-settings'){const f=$('#settings-form');if(f)f.requestSubmit();return}
  if(a==='discard'){await discardOp(mid);return}
  if(a==='retry-op'){await retryOfflineOp(mid);return}
 }catch(e){toast(e.message||'Xatolik',true)}
}
// Guard asynchronous actions so repeated clicks cannot send duplicate
// orders, inventory updates, payments, or account changes.
const pendingButtonActions=new WeakSet();
document.addEventListener('click',e=>{
  const el=e.target.closest('[data-a]');if(!el)return;
  if(el.dataset.a==='modal-overlay'&&e.target!==el)return;
  if(pendingButtonActions.has(el))return;
  pendingButtonActions.add(el);
  const button=el instanceof HTMLButtonElement?el:null;
  if(button)button.disabled=true;
  Promise.resolve().then(()=>doAction(el)).catch(err=>toast(err.message||'Xatolik',true)).finally(()=>{
    pendingButtonActions.delete(el);
    if(button)button.disabled=false;
  });
});
const pendingFormSubmissions=new WeakSet();
document.addEventListener('submit',async e=>{
  const f=e.target;
  if(!f.id.startsWith('pa-')&&!['login-form','modal-form','settings-form'].includes(f.id))return;
  e.preventDefault();
  if(pendingFormSubmissions.has(f))return;
  pendingFormSubmissions.add(f);
  const submit=f.querySelector('[type="submit"]');
  if(submit)submit.disabled=true;
  try{
    if(f.id.startsWith('pa-'))await window.platformSettingsSubmit(f);
    else if(f.id==='login-form'){
      const x=Object.fromEntries(new FormData(f).entries());await login(x.username,x.password);
    }else if(f.id==='modal-form')await onModalSubmit(f);
    else await settingsSave(f);
  }catch(err){toast(err.message||'Xatolik',true)}
  finally{
    pendingFormSubmissions.delete(f);
    if(submit)submit.disabled=false;
  }
});
document.addEventListener('change',async e=>{const t=e.target;
 if(t.id==='pa-logo-file'){await window.platformSettingsLogoChange(t.files[0]);return}
 if(t.dataset.qtyId){const p=state.data.products.find(x=>x.id===t.dataset.qtyId);const q=Number(t.value);if(!p||!Number.isFinite(q)||q<=0||q>(state.data.branch_stock?.[p.id]??p.stock)){toast('Miqdor ombor qoldig‘idan oshmasin',true);render();return}state.cart[p.id]=Math.round(q*100)/100;render();return}
 if(t.dataset.planId){try{await mutate('/stores/'+t.dataset.planId+'/plan',{plan:t.value});toast('Tarif yangilandi')}catch(e){toast(e.message,true)}return}
 if(t.dataset.leadId){try{await mutate('/platform/inquiries/'+t.dataset.leadId+'/status',{status:t.value});toast('Murojaat holati yangilandi')}catch(e){toast(e.message,true)}return}
 if(t.id==='store-select'){await switchShop(t.value);return}
 if(t.id==='branch-select'){if(visibleOutbox().length)return toast('Filial almashtirishdan oldin offline navbatni sinxronlang',true);state.branchId=t.value;localStorage.setItem('donchi-clean-branch',t.value);state.cart={};await load();return}
 if(t.id==='pos-customer'){state.posCustomer=t.value;render();return}
 if(t.id==='logo-input'){await logoChange(t.files[0]);return}
});
document.addEventListener('input',e=>{
 const t=e.target;
 if(t.id==='pos-search'||t.id==='product-search'){
   const value=t.value;state.query=value;const name=t.id;const pos=t.selectionStart;render();const newInput=$('#'+name);if(newInput){newInput.focus();newInput.setSelectionRange(pos,pos)}
 }
});
window.addEventListener('online',()=>{state.online=true;syncQueue()});
window.addEventListener('offline',()=>{state.online=false;render()});
window.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.modal)closeModal();if(e.ctrlKey&&e.key.toLowerCase()==='k'){e.preventDefault();const input=$('#pos-search')||$('#product-search');if(input)input.focus()}});
(async()=>{
 if('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('/sw.js').catch(console.warn);
 try{
   await dbOpen();
   try{
     if(previousSession?.token){
       session=previousSession; const changed=await request('/session/upgrade',{method:'POST',storeId:null});
       session={user:changed.user}; rememberUser(changed.user);
     }else{
       const current=await request('/session',{storeId:null});
       session={user:current.user}; rememberUser(current.user);
     }
   }catch(e){
     if(looksNetwork(e)){
       const user=previousUser()||previousSession?.user;
       if(user){session={user}; state.online=false; state.usingCache=true}
     }else{
       localStorage.removeItem('donchi-clean-last-user');
       session=null;
     }
   }
   previousSession=null;
   if(session){
     adoptAccountStore(session.user);
     if(routePortal())return;
     state.view=menuRole()==='superadmin'?'platform':menuRole()==='seller'?'pos':menuRole()==='warehouse'?'inventory':'dashboard';
     await load();
   }else render();
   if(session&&navigator.onLine&&visibleOutbox().length)syncQueue();
 }catch(e){console.error(e);toast('Ilova ma’lumotlari ochilmadi. Brauzer sozlamalarini tekshiring',true);render()}
})();
