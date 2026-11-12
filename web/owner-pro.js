
'use strict';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>new Intl.NumberFormat('uz-UZ',{maximumFractionDigits:2}).format(Number(v)||0)+' so‘m';
const el=id=>document.getElementById(id);
async function get(path){let r=await fetch('/api/owner-pro/'+path,{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error(r.status===401?'Sessiya tugagan. Saytga qayta kiring.':r.status===403?'Faqat do‘kon egasi bu sahifani ochishi mumkin.':'Ma’lumotni olishda xato: '+r.status);return r.json()}
function table(headers,items){if(!items.length)return '<p class="muted">Hozircha ma’lumot yo‘q.</p>';return '<div class="table-scroll"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+items.map(row=>'<tr>'+row.map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'}
async function load(){el('error').textContent='';el('reload').disabled=true;try{
const [o,i,d,c,a]=await Promise.all(['overview','inventory','receivables','cash','audit'].map(get));
el('store').textContent=o.store.name;
const k=o.kpis;
const cards=[['Bugungi savdo',money(k.today_revenue)],['Jami sof tushum',money(k.net_revenue_all_time)],['Taxminiy foyda',money(k.estimated_profit_all_time)],['Mijoz qarzlari',money(k.receivables)],['Ombor qiymati',money(k.stock_value_at_recorded_cost)],['Kam qolgan tovarlar',String(k.low_stock_count)]];
el('kpis').innerHTML=cards.map(([name,value])=>'<article class="card"><span>'+esc(name)+'</span><strong>'+esc(value)+'</strong></article>').join('');
const max=Math.max(1,...o.weekly_sales.map(x=>Math.max(0,x.revenue)));
el('sales').innerHTML=o.weekly_sales.map(x=>'<div class="bar"><label>'+esc(x.day)+'</label><div class="track"><div class="fill" style="width:'+Math.min(100,Math.max(0,x.revenue)/max*100)+'%"></div></div><small>'+esc(money(x.revenue))+'</small></div>').join('');
el('inventory').innerHTML=table(['Mahsulot','Qoldiq','Minimum'],i.low_stock.map(x=>[x.name,x.stock+' '+x.unit,x.min_stock+' '+x.unit]));
el('debts').innerHTML=table(['Mijoz','Qarz'],d.customers.map(x=>[x.name,money(x.balance)]));
el('cash').innerHTML=table(['Kassir','Holat','Farq'],c.shifts.map(x=>[x.cashier,x.status,x.variance==null?'—':money(x.variance)]));
el('audit').innerHTML=table(['Vaqt','Xodim','Harakat'],a.events.map(x=>[x.created_at,x.username,x.action]));
}catch(e){el('error').textContent=e.message}finally{el('reload').disabled=false}}

let notifOffset=0;
const formatDate=s=>{if(!s)return '—';const date=new Date(s);return Number.isNaN(date.getTime())?s:date.toLocaleString('uz-UZ',{timeZone:'Asia/Tashkent',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});};
function reportRows(data){const names={sales:'Jami savdo',net_sales:'Qaytarishdan keyingi savdo',returns:'Qaytarishlar',cash_sales_after_returns:'Naqd savdo',card_sales_after_returns:'Karta savdosi',new_debt:'Yangi qarzga savdo',debt_payments:'Qarz to‘lovlari',expenses:'Xarajatlar',estimated_profit:'Taxminiy foyda',outstanding_debt:'Jami qarzdorlik',low_stock:'Kam qolgan mahsulotlar',sale_count:'Savdolar soni'};return Object.entries(names).filter(([k])=>data[k]!=null).map(([k,v])=>'<div class="notif-row"><span>'+esc(v)+'</span><strong>'+esc(['sale_count','low_stock'].includes(k)?String(data[k]):money(data[k]))+'</strong></div>').join('');}
async function notifications(reset=false){if(reset)notifOffset=0;try{const r=await get('notifications?offset='+notifOffset+'&limit=20');el('unread-count').textContent=String(r.unread);el('unread-count').hidden=r.unread===0;el('history-meta').textContent=r.total+' ta xabarnoma • '+r.unread+' ta o‘qilmagan';el('history-more').hidden=!r.has_more;
const inner=r.notifications.map(n=>'<article class="notif-item '+(n.read?'':'unread')+'"><div class="notif-top"><strong>'+esc(n.title)+'</strong><span>'+esc(formatDate(n.created_at))+'</span></div><p class="muted">Hisobot sanasi: '+esc(n.report_date)+'</p><details><summary>Barcha hisobotlarni ko‘rish</summary>'+reportRows(n.details)+'</details>'+(n.read?'<span class="read-label">✓ O‘qilgan '+esc(formatDate(n.read_at))+'</span>':'<button class="mark-read" data-id="'+esc(n.id)+'">✓ O‘qildi</button>')+'</article>').join('');
if(reset)el('history-items').innerHTML=inner;else el('history-items').insertAdjacentHTML('beforeend',inner);
if(!r.total)el('history-items').innerHTML='<p class="muted">Hozircha xabarnoma yo‘q. Kunlik hisobotlar soat 20:00 da yaratiladi.</p>';
notifOffset+=r.notifications.length;
}catch(err){el('history-error').textContent=err.message;}}
document.addEventListener('click',async e=>{const btn=e.target.closest('.mark-read');if(!btn)return;btn.disabled=true;try{const result=await fetch('/api/owner-pro/notifications/'+encodeURIComponent(btn.dataset.id)+'/read',{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json'}});if(!result.ok)throw Error('O‘qildi holatini saqlab bo‘lmadi');await notifications(true);}catch(err){el('history-error').textContent=err.message;btn.disabled=false;}});
el('bell').addEventListener('click',()=>{el('notification-history').scrollIntoView({behavior:'smooth',block:'start'});notifications(true);});
el('history-more').addEventListener('click',()=>notifications(false));
el('reload').addEventListener('click',()=>{load();notifications(true);});
load();notifications(true);
setInterval(()=>{if(!document.hidden)notifications(true)},60000);

