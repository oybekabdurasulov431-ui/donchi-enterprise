const form=document.querySelector('#demo-form');const result=document.querySelector('#form-result');
form.addEventListener('submit',async e=>{e.preventDefault();const btn=form.querySelector('button[type="submit"]');btn.disabled=true;result.textContent='Yuborilmoqda…';
const body=Object.fromEntries(new FormData(form).entries());body.consent=!!form.elements.consent.checked;
try{const resp=await fetch('/api/public/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await resp.json();if(!resp.ok){throw new Error(typeof data.detail==='string'?data.detail:'Murojaat yuborilmadi')};form.reset();result.textContent='✓ Murojaatingiz qabul qilindi. Bog‘lanish uchun ma’lumot saqlandi.';result.style.color='#087e61';}
catch(error){result.textContent=error.message||'Ulanishni tekshiring';result.style.color='#a23c2f';}finally{btn.disabled=false;}});
