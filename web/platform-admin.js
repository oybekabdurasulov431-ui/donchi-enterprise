/* DONCHI Super Admin settings (only /platform/). No external dependencies. */
'use strict';
const PA={data:null,tab:'profile',secret:null,logo:null};
const PA_TABS=[['profile','Profil'],['security','Xavfsizlik'],['brand','Platforma'],['plans','Tariflar'],['notifications','Bildirishnomalar'],['audit','Audit'],['backup','Zaxira nusxa'],['monitor','Monitoring']];
const field=(name,label,value='',type='text',attrs='')=>'<div class="form-group"><label>'+esc(label)+'</label><input class="input" name="'+name+'" type="'+type+'" value="'+esc(value)+'" '+attrs+'></div>';
const chk=(key,label,v)=>'<label class="pa-check"><input type="checkbox" name="'+key+'" '+(v?'checked':'')+'>'+esc(label)+'</label>';
const form=(id,fields,button='Saqlash')=>'<form id="pa-'+id+'" class="pa-form">'+fields+'<button type="submit" class="btn">'+ico('save',16)+' '+esc(button)+'</button></form>';
const panel=(title,body,subtitle='')=>'<section class="panel panelpad pa-panel"><h3>'+title+'</h3>'+(subtitle?'<p class="subtitle">'+subtitle+'</p>':'')+body+'</section>';
const note=t=>'<div class="alert mt">'+ico('alert',16)+' '+t+'</div>';
const sessionTime=t=>t?new Date(t*1000).toLocaleString('uz-UZ'):'—';
function platformSettingsPage(){
 const d=PA.data;let body='';
 if(!d){body=panel('Sozlamalar yuklanmoqda','<button class="btn secondary" data-a="pa-refresh">Yangilash</button>');}
 else {
 const p=d.profile,b=d.brand,n=d.notifications;
 switch(PA.tab){
 case 'profile':
  body=panel('Shaxsiy profil',form('profile',field('username','Login',p.username,'text','minlength="4" maxlength="60" required')+field('full_name','Ism va familiya',p.full_name,'text','required')+field('current_password','Tasdiqlash uchun joriy parol','','password','autocomplete="current-password" required')),'Login va ismni o‘zgartirishda joriy parol talab qilinadi.');break;
 case 'security':
  body='<div class="grid-half">'+panel('Parolni almashtirish',form('password',field('old_password','Eski parol','','password','required')+field('new_password','Yangi parol (12+ belgi)','','password','minlength="12" required')+(d.totp_enabled?field('totp','2FA kodi','','text','inputmode="numeric" pattern="[0-9]{6}" required'):''),'Parolni yangilash'),'Yangilanishdan keyin barcha sessiyalardan chiqiladi.')+
   panel('Ikki bosqichli himoya',d.totp_enabled?'<p>'+badge('2FA faol')+'</p>'+form('disable-2fa',field('current_password','Joriy parol','','password','required')+field('code','Authenticator kodi','','text','inputmode="numeric" pattern="[0-9]{6}" required'),'2FA’ni o‘chirish'):
   PA.secret?'<p>Authenticator dasturiga quyidagi maxfiy kalitni kiriting:</p><code class="pa-secret">'+esc(PA.secret)+'</code><p class="subtitle">Ushbu kalitni boshqalarga yubormang.</p>'+form('confirm-2fa',field('code','6 raqamli kod','','text','inputmode="numeric" pattern="[0-9]{6}" required'),'Faollashtirish'):
   '<p>Google Authenticator yoki boshqa TOTP ilovasi bilan ishlaydi.</p><button class="btn secondary" data-a="pa-start-2fa">2FA ni sozlash</button>')+'</div>'+
   panel('Faol qurilmalar',(d.sessions||[]).map(s=>'<div class="pa-row"><span>'+(s.current?'Joriy qurilma':'Boshqa qurilma')+'<small>Oxirgi kirish: '+sessionTime(s.last_seen)+'</small></span>'+badge(s.current?'Siz':'Faol','blue')+'</div>').join('')+'<button class="btn secondary mt" data-a="pa-revoke">Boshqa qurilmalardan chiqish</button>');break;
 case 'brand':
  body=panel('Platforma brendi',form('brand',field('brand_name','Platforma nomi',b.brand_name,'text','required')+field('tagline','Shior',b.tagline)+field('support_phone','Telefon',b.support_phone,'tel')+field('support_email','Email',b.support_email,'email')+'<div class="form-group"><label>Logo PNG/JPG/WEBP, 180 KB gacha</label><img class="pa-logo" id="pa-logo-preview" alt="Logo" src="'+esc(PA.logo===null?(b.logo||'/icon.svg'):(PA.logo||'/icon.svg'))+'"><input id="pa-logo-file" type="file" accept="image/png,image/jpeg,image/webp"><button type="button" class="btn sm secondary" data-a="pa-clear-logo">Logoni o‘chirish</button></div>'),'Super Admin platforma nomi va brend sozlamalari.');break;
 case 'plans':
  body='<div class="grid-half">'+(d.plans||[]).map(p=>panel(esc(p.name),form('plan-'+p.name,field('price','Narx (so‘m)',p.price,'number','min="0" required')+field('days','Muddat (kun)',p.days,'number','min="1" required')+field('max_users','Xodim limiti',p.max_users,'number','min="1" required')+field('max_branches','Filial limiti',p.max_branches,'number','min="1" required')))).join('')+'</div>'+note('Tarif katalogi ishlaydi. Avtomatik to‘lovlar va limitni majburiy qo‘llash hali ulanmagan.');break;
 case 'notifications':
  body=panel('Telegram bildirishnomalari',form('notifications',chk('telegram_enabled','Telegram xabarlarini yoqish',n.telegram_enabled)+field('telegram_chat_id','Telegram Chat ID',n.telegram_chat_id)+chk('notify_new_store','Yangi do‘kon xabari',n.notify_new_store)+chk('notify_service_errors','Server xatosi xabari',n.notify_service_errors))+'<p class="subtitle">Bot tokeni: '+(d.telegram_token_configured?'Render’da mavjud':'Render Environment’da kiritilmagan')+'</p><button class="btn secondary" data-a="pa-telegram-test">Test xabar yuborish</button>','Bot tokenini faqat Render muhitida DONCHI_TELEGRAM_BOT_TOKEN sifatida kiriting.')+note('Real hodisalar bo‘yicha avtomatik Telegram jo‘natish hali integratsiya qilinmagan.');break;
 case 'audit':
  body=panel('Audit tarixi','<div class="pa-table-scroll"><table class="pa-table"><thead><tr><th>Sana</th><th>Kim</th><th>Amal</th><th>Tafsilot</th></tr></thead><tbody>'+(d.audit||[]).map(a=>'<tr><td>'+esc(dt(a.created_at))+'</td><td>'+esc(a.username)+'</td><td>'+esc(a.action)+'</td><td><code>'+esc((a.details||'').slice(0,180))+'</code></td></tr>').join('')+'</tbody></table></div>');break;
 case 'backup':
  body=panel('To‘liq zaxira nusxa','<p>Joriy bazani izchil SQLite backup sifatida yuklab olish mumkin. Faylda parol xeshlari va mijoz ma’lumotlari mavjud — faqat ishonchli joyda saqlang.</p><button class="btn" data-a="pa-backup">'+ico('download',16)+' SQLite nusxani yuklash</button>'+note('Render Free diski vaqtinchalik. Avtomatik zaxira jadvali va backupdan tiklash hali mavjud emas.'));break;
 case 'monitor':
  body=panel('Server monitoringi','<div class="pa-monitor">'+Object.entries({'Ish vaqti (soniya)':d.monitor.uptime_seconds,'Baza (KB)':Math.round(d.monitor.database_bytes/1024),'Disk bo‘sh (MB)':Math.round(d.monitor.disk_available_bytes/1024/1024),'Do‘konlar':d.monitor.counts.stores,'Foydalanuvchilar':d.monitor.counts.users,'Savdolar':d.monitor.counts.sales,'Mahsulotlar':d.monitor.counts.products,'Audit yozuvlari':d.monitor.counts.audit}).map(([k,v])=>'<div class="pa-stat"><small>'+esc(k)+'</small><strong>'+esc(v)+'</strong></div>').join('')+'</div><p class="subtitle">'+esc(d.monitor.mode)+' · '+esc(d.monitor.server_time)+'</p><button class="btn secondary" data-a="pa-refresh">Yangilash</button>');break;
 }
 }
 return head('Super Admin sozlamalari','Profil, xavfsizlik, platforma, tarif, audit va monitoring')+'<nav class="pa-tabs">'+PA_TABS.map(([k,v])=>'<button class="pa-tab '+(PA.tab===k?'active':'')+'" data-a="pa-tab" data-v="'+k+'">'+v+'</button>').join('')+'</nav>'+body;
}
async function platformSettingsLoad(){try{PA.data=await request('/platform-admin/settings',{storeId:null});render()}catch(e){toast(e.message,true);render()}}
async function platformSettingsAction(el){
 try{
 const a=el.dataset.a;
 if(a==='pa-tab'){PA.tab=el.dataset.v;PA.secret=null;render();return}
 if(a==='pa-refresh'){await platformSettingsLoad();return}
 if(a==='pa-clear-logo'){PA.logo='';const img=document.getElementById('pa-logo-preview');if(img)img.src='/icon.svg';return}
 if(a==='pa-revoke'){if(!confirm('Boshqa qurilmalarni chiqarasizmi?'))return;await request('/platform-admin/sessions/revoke-others',{method:'POST',storeId:null});toast('Boshqa qurilmalar chiqarildi');await platformSettingsLoad();return}
 if(a==='pa-start-2fa'){const r=await request('/platform-admin/2fa/start',{method:'POST',storeId:null});PA.secret=r.secret;render();return}
 if(a==='pa-telegram-test'){await request('/platform-admin/notifications/test',{method:'POST',storeId:null});toast('Xabar yuborildi');return}
 if(a==='pa-backup'){
   if(!confirm('Backup ichida maxfiy ma’lumotlar bo‘lishi mumkin. Yuklab olasizmi?'))return;
   const resp=await fetch('/api/platform-admin/backup',{credentials:'same-origin',cache:'no-store'});
   if(!resp.ok){let err='Backup xatosi';try{err=(await resp.json()).detail||err}catch{}throw Error(err)}
   const url=URL.createObjectURL(await resp.blob()),link=document.createElement('a');
   link.href=url;link.download='DONCHI-backup-'+new Date().toISOString().slice(0,10)+'.sqlite3';link.click();
   setTimeout(()=>URL.revokeObjectURL(url),8000);toast('Backup yuklandi');await platformSettingsLoad();return;
 }
 }catch(e){toast(e.message||'Xatolik',true)}
}
async function platformSettingsSubmit(formEl){
 const name=formEl.id;
 const x=Object.fromEntries(new FormData(formEl).entries());
 try{
 if(name==='pa-profile'){
   const r=await request('/platform-admin/profile',{method:'PUT',body:x,storeId:null});
   session.user.username=r.user.username;session.user.full_name=r.user.full_name;rememberUser(session.user);
 }else if(name==='pa-brand'){
   x.logo=PA.logo===null?PA.data.brand.logo:PA.logo;
   await request('/platform-admin/brand',{method:'PUT',body:x,storeId:null});PA.logo=null;
 }else if(name.startsWith('pa-plan-')){
   const plan=name.slice('pa-plan-'.length);
   const body=Object.fromEntries(Object.entries(x).map(([k,v])=>[k,Number(v)]));
   await request('/platform-admin/plans/'+encodeURIComponent(plan),{method:'PUT',body,storeId:null});
 }else if(name==='pa-notifications'){
   ['telegram_enabled','notify_new_store','notify_service_errors'].forEach(k=>x[k]=!!formEl.elements[k]?.checked);
   await request('/platform-admin/notifications',{method:'PUT',body:x,storeId:null});
 }else if(name==='pa-password'){
   if(x.new_password.length<12)throw Error('Kamida 12 belgili parol tanlang');
   await request('/account/password',{method:'POST',body:x,storeId:null});
   logout('Parol o‘zgardi, qayta kiring');return;
 }else if(name==='pa-confirm-2fa'){
   await request('/platform-admin/2fa/confirm',{method:'POST',body:x,storeId:null});PA.secret=null;
 }else if(name==='pa-disable-2fa'){
   if(!confirm('2FA himoyasini o‘chirasizmi?'))return;
   await request('/platform-admin/2fa/disable',{method:'POST',body:x,storeId:null});
 }else return;
 toast('Sozlamalar saqlandi');await platformSettingsLoad();
 }catch(e){toast(e.message||'Xatolik',true)}
}
async function platformSettingsLogoChange(file){
 if(!file)return;
 if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>180000){toast('PNG/JPG/WEBP 180KB gacha',true);return}
 const r=new FileReader();r.onload=()=>{PA.logo=r.result;const img=document.getElementById('pa-logo-preview');if(img)img.src=r.result};r.readAsDataURL(file);
}
window.platformSettingsPage=platformSettingsPage;
window.platformSettingsLoad=platformSettingsLoad;
window.platformSettingsAction=platformSettingsAction;
window.platformSettingsSubmit=platformSettingsSubmit;
window.platformSettingsLogoChange=platformSettingsLogoChange;
window.platformAdmin=PA;
