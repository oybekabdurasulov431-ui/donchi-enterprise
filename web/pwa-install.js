/* DONCHI Universal PWA install experience.
   A browser, not the website, decides if native installation is available.
   Never claim the app was installed before appinstalled/standalone confirms it.
*/
'use strict';
(() => {
  let promptEvent = null;
  let installed = window.matchMedia('(display-mode: standalone)').matches ||
                  window.navigator.standalone === true;
  const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const hasInstaller = () => Boolean(promptEvent);
  const label = () => installed ? 'Ilova o‘rnatilgan' :
      hasInstaller() ? 'Ilovani o‘rnatish' : 'O‘rnatish';
  const canInstall = () => !installed;
  const button = (compact=false) => {
    return '<button type="button" class="donchi-install-btn'+(compact?' compact':'')+
      '" data-pwa-install data-a="install-app"'+(installed?' disabled':'')+
      ' aria-label="'+label()+'">'+
      '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'+
      (installed?'<path d="m4 12 5 5L20 6"/>':'<path d="M12 3v12m-5-5 5 5 5-5M4 18v3h16v-3"/>')+
      '</svg><span>'+label()+'</span></button>';
  };
  const refresh = () => {
    document.querySelectorAll('[data-pwa-install]').forEach(btn=>{
      btn.disabled=installed;
      btn.setAttribute('aria-label',label());
      const span=btn.querySelector('span');
      if(span)span.textContent=label();
    });
  };
  function showToast(message){
    const parent=document.querySelector('#toasts');
    if(!parent)return;
    const el=document.createElement('div');
    el.className='toast';el.setAttribute('role','status');el.textContent=message;
    parent.appendChild(el);setTimeout(()=>el.remove(),5000);
  }
  function showGuide(){
    const ios=isIOS();
    const old=document.querySelector('#donchi-install-guide');
    if(old)old.remove();
    const veil=document.createElement('div');
    veil.id='donchi-install-guide';veil.className='donchi-install-overlay';
    veil.innerHTML='<section class="donchi-install-card" role="dialog" aria-modal="true" aria-labelledby="donchi-install-title">'+
      '<div class="install-symbol" aria-hidden="true">D</div>'+
      '<h2 id="donchi-install-title">DONCHI ilovasini o‘rnatish</h2>'+
      '<p>'+(ios?
      'iPhone yoki iPad’da Safari’ning <b>Ulashish (Share)</b> tugmasini bosing va <b>Add to Home Screen / Asosiy ekranga qo‘shish</b> bandini tanlang.':
      'Brauzer menyusidan <b>Install app / Ilovani o‘rnatish</b> yoki <b>Asosiy ekranga qo‘shish</b> bandini tanlang. Bu brauzerga va qurilmaga bog‘liq.')+
      '</p><p class="install-guide-note">O‘rnatish tugmasi faqat brauzer ruxsat berganda avtomatik o‘rnatish oynasini ochadi.</p>'+
      '<button class="btn block" type="button" data-close-install>Tushunarli</button></section>';
    document.body.appendChild(veil);
    const close=()=>veil.remove();
    veil.querySelector('[data-close-install]').addEventListener('click',close);
    veil.addEventListener('click',e=>{if(e.target===veil)close()});
    document.addEventListener('keydown',function onEscape(e){if(e.key==='Escape'){close();document.removeEventListener('keydown',onEscape)}});
    veil.querySelector('button').focus();
  }
  async function install(){
    if(installed){showToast('DONCHI ilova sifatida ochilgan');return}
    if(!promptEvent){showGuide();return}
    const event=promptEvent;promptEvent=null;
    try{
      await event.prompt();
      const choice=await event.userChoice;
      if(choice?.outcome==='accepted'){
        showToast('O‘rnatish tasdiqlandi — ilovaning o‘rnatilishini tekshiring');
      }else{
        showToast('O‘rnatish bekor qilindi. Keyinroq qayta urinishingiz mumkin');
      }
    }catch(error){
      console.warn('PWA install unavailable',error);
      showGuide();
    }finally{refresh()}
  }
  window.addEventListener('beforeinstallprompt',event=>{
    event.preventDefault();promptEvent=event;installed=false;refresh();
  });
  window.addEventListener('appinstalled',()=>{
    promptEvent=null;installed=true;refresh();
    showToast('DONCHI muvaffaqiyatli o‘rnatildi');
  });
  document.addEventListener('click',event=>{
    const target=event.target.closest('[data-a="install-app"]');
    if(!target)return;
    event.preventDefault();
    event.stopImmediatePropagation();
    install();
  },true);
  window.DONCHI_PWA={button,refresh,install,canInstall,isInstalled:()=>installed,hasPrompt:hasInstaller};
})();
