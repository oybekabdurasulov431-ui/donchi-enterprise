'use strict';
const names=[['profile','Profil'],['security','Xavfsizlik'],['brand','Platforma'],['plans','Tariflar'],['notifications','Bildirishnomalar'],['audit','Audit'],['backup','Zaxira nusxa'],['monitor','Monitoring']];
const S={tab:'profile',data:null,secret:'',newLogo:null};
const el=id=>document.getElementById(id);
const escapeHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const field=(n,label,v='',type='text',attrs='')=>'<label class="field">'+escapeHtml(label)+'<input name="'+n+'" type="'+type+'" value="'+escapeHtml(v)+'" '+attrs+'></label>';
const checkbox=(n,label,v)=>'<label class="check"><input name="'+n+'" type="checkbox" '+(v?'checked':'')+'>'+escapeHtml(label)+'</label>';
const button=(label,secondary=false,type='button',action='')=>'<button type="'+type+'" class="action '+(secondary?'secondary':'')+'" '+(action?'data-action="'+action+'"':'')+'>'+escapeHtml(label)+'</button>';
const card=(title,contents,desc='')=>'<section class="card"><h2>'+escapeHtml(title)+'</h2>'+(desc?'<p>'+escapeHtml(desc)+'</p>':'')+contents+'</section>';
const form=(name,fields,label='Saqlash')=>'<form data-form="'+name+'">'+fields+button(label,false,'submit')+'</form>';
const stat=(label,value)=>'<div class="stat"><small>'+escapeHtml(label)+'</small><b>'+escapeHtml(value)+'</b></div>';
function flash(message,isError=false){const m=el('message');m.textContent=message;m.className=isError?'error':'';m.style.display='block';m.scrollIntoView({behavior:'smooth',block:'nearest'})}
async function api(path,method='GET',body){
 const response=await fetch('/api'+path,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 if(!response.ok){let detail='HTTP '+response.status;try{const x=await response.json();detail=x.detail||detail}catch{}throw Error(detail)}
 return response.json();
}
function render(){
 el('tabs').innerHTML=names.map(([id,title])=>'<button class="tab '+(id===S.tab?'active':'')+'" data-tab="'+id+'">'+title+'</button>').join('');
 if(!S.data){el('content').innerHTML=card('Yuklanmoqda','<p>Serverdan ma’lumot olinmoqda...</p>');return}
 const d=S.data, p=d.profile, b=d.brand, n=d.notifications, m=d.monitor;let html='';
 switch(S.tab){
 case 'profile':
  html=card('Super Admin profili',form('profile',field('username','Login',p.username,'text','minlength="4" required')+field('full_name','Ism-familiya',p.full_name,'text','required')+field('current_password','Joriy parol','','password','autocomplete="current-password" required')),'Loginni o‘zgartirish uchun joriy parolni tasdiqlang.');break;
 case 'security':
  html='<div class="grid">'+card('Parolni o‘zgartirish',form('password',field('old_password','Joriy parol','','password','required')+field('new_password','Yangi parol (kamida 12 belgi)','','password','minlength="12" required')+(d.totp_enabled?field('totp','2FA kodi','','text','inputmode="numeric" pattern="[0-9]{6}" required'):''),'Parolni yangilash'),'Parol yangilanganda qayta kirish kerak bo‘ladi.')+
  card('Ikki bosqichli himoya',d.totp_enabled?'<p>✅ 2FA faol</p>'+form('disable2fa',field('current_password','Joriy parol','','password','required')+field('code','6 raqamli kod','','text','pattern="[0-9]{6}" required'),'2FA ni o‘chirish'):(S.secret?'<p>Authenticator ilovasiga maxfiy kalitni kiriting:</p><code>'+escapeHtml(S.secret)+'</code>'+form('confirm2fa',field('code','6 raqamli kod','','text','pattern="[0-9]{6}" required'),'2FA ni yoqish'):button('Authenticator orqali 2FA sozlash',true,'button','start2fa')),'2FA kodi har 30 soniyada yangilanadi.')+'</div>'+
  card('Faol qurilmalar',(d.sessions||[]).map(x=>'<p>'+escapeHtml(x.current?'Joriy qurilma':'Boshqa qurilma')+' — '+escapeHtml(x.last_seen?new Date(x.last_seen*1000).toLocaleString('uz-UZ'):'—')+'</p>').join('')+button('Boshqa qurilmalardan chiqish',true,'button','revoke'));break;
 case 'brand':
  html=card('Platforma ma’lumotlari',form('brand',field('brand_name','Nomi',b.brand_name,'text','required')+field('tagline','Shior',b.tagline)+field('support_phone','Telefon',b.support_phone,'tel')+field('support_email','Email',b.support_email,'email')+'<label class="field">Logo PNG/JPG/WEBP (180 KB gacha)<input type="file" id="brand-logo" accept="image/png,image/jpeg,image/webp"></label>'));break;
 case 'plans':
  html='<div class="grid">'+d.plans.map(x=>card(x.name,form('plan:'+x.name,field('price','Narx (so‘m)',x.price,'number','min="0" max="100000000" required')+field('days','Muddat (kun)',x.days,'number','min="1" max="730" required')+field('max_users','Xodimlar soni',x.max_users,'number','min="1" required')+field('max_branches','Filiallar soni',x.max_branches,'number','min="1" required')))).join('')+'</div><p class="notice">Tarif katalogi saqlanadi. Avtomatik billing va tarif limitlarining to‘liq nazorati hali ulanmagan.</p>';break;
 case 'notifications':
  html=card('Telegram va ogohlantirishlar',form('notifications',checkbox('telegram_enabled','Telegramni yoqish',n.telegram_enabled)+field('telegram_chat_id','Telegram Chat ID',n.telegram_chat_id)+checkbox('notify_new_store','Yangi do‘kon haqida xabar',n.notify_new_store)+checkbox('notify_service_errors','Server xatolari haqida xabar',n.notify_service_errors))+ '<p>Bot tokeni: '+(d.telegram_token_configured?'mavjud':'Render’da o‘rnatilmagan')+'</p>'+button('Telegram test xabari',true,'button','telegramtest'))+'<div class="notice">Test xabar ishlashi mumkin; avtomatik voqea xabarlari hali ulanmagan.</div>';break;
 case 'audit':
  html=card('Oxirgi amallar','<div style="overflow:auto"><table><thead><tr><th>Vaqt</th><th>Foydalanuvchi</th><th>Amal</th></tr></thead><tbody>'+(d.audit||[]).map(x=>'<tr><td>'+escapeHtml(x.created_at)+'</td><td>'+escapeHtml(x.username)+'</td><td>'+escapeHtml(x.action)+'</td></tr>').join('')+'</tbody></table></div>');break;
 case 'backup':
  html=card('Ma’lumotlar bazasi nusxasi','<p>Bazada do‘konlar va mijozlarning maxfiy ma’lumotlari bor. Yuklangan faylni himoyalangan joyda saqlang.</p>'+button('SQLite bazani yuklab olish',false,'button','backup')+'<div class="notice">Render Free’da baza vaqtincha. Avtomatik backup va serverda tiklash hali mavjud emas.</div>');break;
 case 'monitor':
  html=card('Server monitoringi','<div class="grid">'+Object.entries({'Ish vaqti (soniya)':m.uptime_seconds,'Baza (KB)':Math.ceil(m.database_bytes/1024),'Disk (MB)':Math.floor(m.disk_available_bytes/1048576),'Do‘konlar':m.counts.stores,'Foydalanuvchilar':m.counts.users,'Savdolar':m.counts.sales,'Mahsulotlar':m.counts.products}).map(([a,v])=>stat(a,v)).join('')+'</div><p>'+escapeHtml(m.mode)+' — '+escapeHtml(m.server_time)+'</p>'+
  '<div class="notice"><strong>Saqlash holati:</strong> '+escapeHtml(m.storage_warning||'Saqlash holatini tekshiring')+
  '<p>Baza yaxlitligi: '+escapeHtml(m.integrity_check||'noma’lum')+
  ' · Avtomatik tashqi backup: '+(m.automatic_offsite_backup?'faol':'mavjud emas')+'</p></div>'+
  button('Yangilash',true,'button','reload'));break;
 }
 el('content').innerHTML=html;
}
async function reload(){try{S.data=await api('/platform-admin/settings');render()}catch(e){el('content').innerHTML=card('Sozlamalarni ochib bo‘lmadi','<p>'+escapeHtml(e.message)+'</p><a href="/platform/">Avval Super Admin paneliga kiring</a>');flash(e.message,true)}}
document.addEventListener('click',async event=>{
 const tab=event.target.closest('[data-tab]');if(tab){S.tab=tab.dataset.tab;render();return}
 const action=event.target.closest('[data-action]')?.dataset.action;if(!action)return;
 try{
  if(action==='reload')return reload();
  if(action==='start2fa'){S.secret=(await api('/platform-admin/2fa/start','POST')).secret;render();return}
  if(action==='revoke'){if(confirm('Boshqa barcha qurilmalardan chiqilsinmi?')){await api('/platform-admin/sessions/revoke-others','POST');flash('Boshqa sessiyalar tugatildi');await reload()}return}
  if(action==='telegramtest'){await api('/platform-admin/notifications/test','POST');flash('Test xabar yuborildi');return}
  if(action==='backup'){
   const r=await fetch('/api/platform-admin/backup',{credentials:'same-origin',cache:'no-store'});
   if(!r.ok)throw Error('Backup HTTP '+r.status);
   const url=URL.createObjectURL(await r.blob()),link=document.createElement('a');link.href=url;link.download='DONCHI-backup-'+new Date().toISOString().slice(0,10)+'.sqlite3';link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);flash('Backup yuklab olindi');return
  }
 }catch(e){flash(e.message,true)}
});
document.addEventListener('change',event=>{
 if(event.target.id!=='brand-logo')return;
 const file=event.target.files[0];if(!file)return;
 if(file.size>180000||!['image/png','image/jpeg','image/webp'].includes(file.type)){flash('Logo PNG/JPG/WEBP va 180 KB gacha bo‘lishi kerak',true);event.target.value='';return}
 const r=new FileReader();r.onload=()=>{S.newLogo=r.result};r.readAsDataURL(file)
});
document.addEventListener('submit',async event=>{
 const f=event.target.closest('[data-form]');if(!f)return;event.preventDefault();
 const kind=f.dataset.form, values=Object.fromEntries(new FormData(f).entries());
 const pressed=f.querySelector('[type="submit"]');pressed.disabled=true;
 try{
  let url='',method='PUT',body=values;
  if(kind==='profile')url='/platform-admin/profile';
  else if(kind==='password'){url='/account/password';method='POST';if(values.new_password.length<12)throw Error('Yangi parol kamida 12 belgidan iborat bo‘lsin')}
  else if(kind==='brand'){url='/platform-admin/brand';body.logo=S.newLogo===null?S.data.brand.logo:S.newLogo}
  else if(kind.startsWith('plan:')){url='/platform-admin/plans/'+encodeURIComponent(kind.slice(5));for(const key of Object.keys(body))body[key]=Number(body[key])}
  else if(kind==='notifications'){url='/platform-admin/notifications';for(const key of ['telegram_enabled','notify_new_store','notify_service_errors'])body[key]=!!f.elements[key]?.checked}
  else if(kind==='confirm2fa'){url='/platform-admin/2fa/confirm';method='POST'}
  else if(kind==='disable2fa'){url='/platform-admin/2fa/disable';method='POST';if(!confirm('2FA ni o‘chirasizmi?'))return}
  else return;
  await api(url,method,body);S.newLogo=null;S.secret='';
  if(kind==='password'){flash('Parol o‘zgardi. Super Admin paneliga qayta kir.');S.data=null;return}
  await reload();flash('Sozlamalar saqlandi')
 }catch(e){flash(e.message,true)}
 finally{pressed.disabled=false}
});
reload();
