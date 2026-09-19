(()=>{
  const USED_KEY='free-bet-tracker-used-v1';
  const BRIDGE_CONFIG_URL='https://raw.githubusercontent.com/tucknub/nfl-prop-war-room/streamlit-cloud-deploy/free-bet-tracker/bridge-config.json';
  let bridgeUrl='';

  try{
    const style=document.createElement('style');
    style.textContent=`
      .attention.upnext{background:linear-gradient(135deg,#261b3b,#5b378b)!important;border-color:rgba(181,140,255,.28)!important}
      .attention.upnext .attentionBang{background:rgba(142,99,255,.2)!important}
      .attention.upnext:after{opacity:.45}
      .firstFlag{display:none!important}
      details.card.first:not(.finalHour):not(.critical) .firstFlag{display:block!important}

      .logoTile:has(img[src*="CaesarsSportsbook"]){width:92px!important;height:58px!important;flex:0 0 92px!important;border-radius:16px!important;padding:8px 10px!important}
      .logoTile:has(img[src*="CaesarsSportsbook"]) img{display:block!important;width:82px!important;height:auto!important;max-width:none!important;max-height:34px!important;object-fit:contain!important;margin:auto!important}
      .railLogo img[src*="Hard-Rock-Bet"]{max-width:66%!important;max-height:42px!important}
      .railLogo img[src*="CaesarsSportsbook"]{max-width:88%!important;max-height:42px!important}
      .railLogo img[src*="Sportsbook_FC_on_dark"]{max-width:68%!important;max-height:42px!important}
      .railLogo img[src*="Bet365_Logo"]{max-width:64%!important;max-height:34px!important}

      .usedAction{display:flex;align-items:center;justify-content:flex-end;margin-top:14px;padding-top:13px;border-top:1px solid rgba(181,140,255,.12)}
      .usedButton{appearance:none;border:1px solid rgba(114,226,156,.28);background:linear-gradient(145deg,rgba(114,226,156,.14),rgba(142,99,255,.08));color:#baf2ce;border-radius:11px;padding:9px 12px;font:inherit;font-size:11px;font-weight:900;letter-spacing:.02em;cursor:pointer;box-shadow:inset 0 0 14px rgba(114,226,156,.04)}
      .usedButton:hover{border-color:rgba(114,226,156,.48);background:linear-gradient(145deg,rgba(114,226,156,.2),rgba(142,99,255,.1))}
      .usedButton:active{transform:scale(.98)}
      .usedToast{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:100;width:min(420px,calc(100% - 28px));display:flex;align-items:center;gap:12px;padding:12px 13px;border-radius:15px;background:rgba(18,13,25,.97);border:1px solid rgba(181,140,255,.24);box-shadow:0 18px 48px rgba(0,0,0,.48),0 0 22px rgba(142,99,255,.12);backdrop-filter:blur(16px);color:#f7f4ff}
      .usedToastText{min-width:0;flex:1;font-size:11px;font-weight:800;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .usedUndo{appearance:none;border:1px solid rgba(181,140,255,.22);background:rgba(142,99,255,.14);color:#d9c8ff;border-radius:9px;padding:7px 10px;font:inherit;font-size:10px;font-weight:950;cursor:pointer}

      @media(max-width:759px){.usedAction{justify-content:stretch}.usedButton{width:100%;padding:11px 12px;font-size:12px}}
      @media(min-width:760px){
        .app{max-width:880px!important;padding-left:24px!important;padding-right:24px!important;padding-bottom:52px!important}
        .hero{padding:24px 24px 22px!important;border-radius:30px!important}
        .top h1{font-size:34px!important;letter-spacing:-.045em!important}
        .top p{font-size:14px!important;margin-top:10px!important}
        .titleBox{padding-left:62px!important;min-height:54px!important}
        .appIcon{width:51px!important;height:51px!important;border-radius:16px!important;top:-3px!important}
        .refresh{width:50px!important;height:50px!important;border-radius:16px!important;font-size:23px!important}
        .liveRow{margin-top:18px!important;font-size:12px!important}
        .logoRail{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:14px!important;margin-top:15px!important;align-items:center!important}
        .railLogo{height:58px!important;border-radius:17px!important;padding:8px 14px!important}
        .railLogo img{display:block!important;width:auto!important;height:auto!important;max-width:78%!important;max-height:38px!important;object-fit:contain!important;transform:none!important;margin:auto!important}
        .railLogo img[src*="Hard-Rock-Bet"]{max-width:62%!important;max-height:42px!important}
        .railLogo img[src*="CaesarsSportsbook"]{max-width:90%!important;max-height:44px!important}
        .railLogo img[src*="Sportsbook_FC_on_dark"]{max-width:66%!important;max-height:42px!important}
        .railLogo img[src*="Bet365_Logo"]{max-width:62%!important;max-height:34px!important}
        .railCount{min-width:21px!important;height:21px!important;font-size:10px!important}
        .railNext{font-size:8px!important;padding:4px 8px!important;bottom:-8px!important}
        .attention{margin:16px 0 18px!important;padding:20px 22px!important;border-radius:24px!important}
        .attentionTop{grid-template-columns:46px minmax(0,1fr) auto!important;gap:14px!important}
        .attentionBang{width:46px!important;height:46px!important;border-radius:15px!important;font-size:27px!important}
        .attentionLabel{font-size:12px!important}.attentionPromo{font-size:20px!important}.attentionTimer{font-size:31px!important}
        .attentionBottom{margin-top:14px!important;padding-top:13px!important}.attentionReason{font-size:13px!important;max-width:76%!important}.attentionWhen{font-size:11px!important}
        .summary{grid-template-columns:1.28fr 1fr!important;gap:14px!important;margin:16px 0 12px!important}
        .stat{padding:18px 18px!important;border-radius:21px!important;min-height:126px!important}.statMark{width:35px!important;height:35px!important;right:15px!important;top:15px!important;border-radius:11px!important}.statMark svg{width:20px!important;height:20px!important}
        .label{font-size:11px!important}.num{font-size:34px!important;margin-top:8px!important}.statSub{font-size:11px!important;margin-top:6px!important}.meta{font-size:12.5px!important;margin:0 4px 28px!important}
        .sectionRow{margin:6px 4px 14px!important}.section{font-size:19px!important}.section:before{font-size:9px!important;margin-bottom:5px!important}.subtle{font-size:12px!important}
        .list{gap:14px!important}details.card{border-radius:24px!important}summary{padding:20px 20px 17px 24px!important}.cardTop{gap:16px!important;align-items:center!important}
        .logoTile{width:68px!important;height:68px!important;flex-basis:68px!important;border-radius:19px!important;padding:9px!important}.logoTile:has(img[src*="CaesarsSportsbook"]){width:122px!important;height:68px!important;flex:0 0 122px!important;padding:8px 12px!important;border-radius:19px!important}.logoTile:has(img[src*="CaesarsSportsbook"]) img{width:108px!important;max-width:none!important;max-height:40px!important}
        .book{font-size:12px!important}.heroValue{font-size:25px!important}.promo{font-size:18px!important;margin-top:7px!important}.typeLine{margin-top:10px!important}.tapHint{font-size:12px!important}.typeIcon{width:25px!important;height:25px!important;border-radius:8px!important}
        .foot{margin-top:16px!important;padding-top:13px!important;align-items:center!important}.count{font-size:17px!important;min-height:36px!important;padding:7px 12px!important}.exact{font-size:12px!important;margin-top:5px!important}.pill{font-size:10px!important;padding:7px 10px!important}.details{padding:16px 20px 19px 24px!important;font-size:13px!important}.detailLabel{font-size:10.5px!important}.note{font-size:11.5px!important;margin-top:24px!important}
      }
    `;
    document.head.appendChild(style);
  }catch{}

  function readUsed(){
    try{return new Set(JSON.parse(localStorage.getItem(USED_KEY)||'[]').map(String))}catch{return new Set()}
  }
  function writeUsed(set){try{localStorage.setItem(USED_KEY,JSON.stringify([...set]))}catch{}}

  async function loadBridgeConfig(){
    try{
      const r=await fetch(BRIDGE_CONFIG_URL+'?ts='+Date.now(),{cache:'no-store'});
      if(!r.ok)return false;
      const cfg=await r.json();
      bridgeUrl=String((cfg&&cfg.bridgeUrl)||'').trim();
      if(!bridgeUrl)return false;
      await syncUsedFromSheet(true);
      return true;
    }catch{return false}
  }

  function bridgeList(){
    return new Promise((resolve,reject)=>{
      if(!bridgeUrl){resolve(null);return}
      const cb='__fbtBridge_'+Date.now()+'_'+Math.random().toString(36).slice(2);
      const s=document.createElement('script');
      let finished=false;
      const cleanup=()=>{if(finished)return;finished=true;try{s.remove()}catch{};try{delete window[cb]}catch{}};
      const timeout=setTimeout(()=>{cleanup();reject(new Error('bridge timeout'))},8000);
      window[cb]=payload=>{clearTimeout(timeout);cleanup();resolve(payload)};
      s.onerror=()=>{clearTimeout(timeout);cleanup();reject(new Error('bridge load failed'))};
      const join=bridgeUrl.includes('?')?'&':'?';
      s.src=bridgeUrl+join+'action=list&callback='+encodeURIComponent(cb)+'&ts='+Date.now();
      document.head.appendChild(s);
    });
  }

  async function syncUsedFromSheet(reloadPromos){
    try{
      const data=await bridgeList();
      if(!data||!Array.isArray(data.promos))return false;
      const sheetUsed=new Set(data.promos.filter(p=>p&&p.used).map(p=>String(p.id||''))).delete('');
      const cleanUsed=new Set(data.promos.filter(p=>p&&p.used&&p.id).map(p=>String(p.id)));
      writeUsed(cleanUsed);
      if(reloadPromos&&typeof load==='function')await load();
      else{pruneUsed();if(typeof render==='function')render()}
      return true;
    }catch{return false}
  }

  async function syncUsedToSheet(id,used){
    if(!bridgeUrl||!id)return false;
    try{
      const body=new URLSearchParams({action:'used',id:String(id),used:String(Boolean(used))});
      await fetch(bridgeUrl,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body});
      setTimeout(()=>syncUsedFromSheet(true),1800);
      return true;
    }catch{return false}
  }

  function pruneUsed(){
    try{
      if(typeof promos==='undefined'||!Array.isArray(promos))return false;
      const used=readUsed();
      if(!used.size)return false;
      const before=promos.length;
      promos=promos.filter(p=>!used.has(String(p.id)));
      return promos.length!==before;
    }catch{return false}
  }
  function addUsedButtons(){
    try{
      document.querySelectorAll('details.card[data-id]').forEach(card=>{
        if(card.querySelector('.usedAction'))return;
        const details=card.querySelector('.details');
        if(!details)return;
        const row=document.createElement('div');
        row.className='usedAction';
        row.innerHTML='<button type="button" class="usedButton">✓ Mark Used</button>';
        row.querySelector('button').addEventListener('click',e=>{
          e.preventDefault();e.stopPropagation();markUsed(String(card.dataset.id||''));
        });
        details.appendChild(row);
      });
    }catch{}
  }
  function markUsed(id){
    if(!id)return;
    let removed=null;
    try{
      if(typeof promos!=='undefined'&&Array.isArray(promos))removed=promos.find(p=>String(p.id)===id)||null;
      const used=readUsed();used.add(id);writeUsed(used);
      if(typeof promos!=='undefined'&&Array.isArray(promos))promos=promos.filter(p=>String(p.id)!==id);
      if(typeof render==='function')render();
      syncUsedToSheet(id,true);
      showUndo(id,removed);
    }catch{}
  }
  function showUndo(id,promo){
    document.querySelector('.usedToast')?.remove();
    const toast=document.createElement('div');
    toast.className='usedToast';
    toast.innerHTML='<div class="usedToastText">Marked used'+(promo&&promo.promo?' · '+String(promo.promo):'')+'</div><button type="button" class="usedUndo">Undo</button>';
    document.body.appendChild(toast);
    const timer=setTimeout(()=>toast.remove(),10000);
    toast.querySelector('.usedUndo').onclick=()=>{
      clearTimeout(timer);
      const used=readUsed();used.delete(id);writeUsed(used);
      try{if(promo&&typeof promos!=='undefined'&&Array.isArray(promos)&&!promos.some(p=>String(p.id)===id))promos.push(promo)}catch{}
      syncUsedToSheet(id,false);
      toast.remove();
      try{if(typeof render==='function')render()}catch{}
    };
  }

  try{
    if(typeof render==='function'){
      const baseRender=render;
      render=function(){pruneUsed();baseRender();addUsedButtons()};
    }
  }catch{}

  window.addEventListener('storage',()=>{try{pruneUsed();if(typeof render==='function')render()}catch{}});
  window.addEventListener('focus',()=>{if(bridgeUrl)syncUsedFromSheet(true)});
  setTimeout(()=>{try{pruneUsed();if(typeof render==='function')render();else addUsedButtons()}catch{}},150);
  setTimeout(loadBridgeConfig,350);
  setInterval(()=>{if(bridgeUrl)syncUsedFromSheet(true)},60000);
})();
