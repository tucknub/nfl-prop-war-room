(()=>{
  const CONFIG_URL='https://raw.githubusercontent.com/tucknub/nfl-prop-war-room/streamlit-cloud-deploy/free-bet-tracker/bridge-config.json';
  const USED_KEY='free-bet-tracker-used-v1';
  const fallbackLoad=typeof load==='function'?load:null;
  let bridgeUrl='';
  let configuring=null;

  async function configure(){
    if(bridgeUrl)return true;
    if(configuring)return configuring;
    configuring=(async()=>{
      try{
        const r=await fetch(CONFIG_URL+'?ts='+Date.now(),{cache:'no-store'});
        if(!r.ok)return false;
        const cfg=await r.json();
        bridgeUrl=String((cfg&&cfg.bridgeUrl)||'').trim();
        return Boolean(bridgeUrl);
      }catch{return false}
      finally{configuring=null}
    })();
    return configuring;
  }

  function bridgeList(){
    return new Promise((resolve,reject)=>{
      if(!bridgeUrl){reject(new Error('bridge not configured'));return}
      const cb='__fbtSheet_'+Date.now()+'_'+Math.random().toString(36).slice(2);
      const s=document.createElement('script');
      let done=false;
      const cleanup=()=>{if(done)return;done=true;try{s.remove()}catch{};try{delete window[cb]}catch{}};
      const timeout=setTimeout(()=>{cleanup();reject(new Error('Sheet bridge timeout'))},8000);
      window[cb]=payload=>{clearTimeout(timeout);cleanup();resolve(payload)};
      s.onerror=()=>{clearTimeout(timeout);cleanup();reject(new Error('Sheet bridge failed'))};
      const join=bridgeUrl.includes('?')?'&':'?';
      s.src=bridgeUrl+join+'action=list&callback='+encodeURIComponent(cb)+'&ts='+Date.now();
      document.head.appendChild(s);
    });
  }

  function setUsedStatus(rows){
    try{
      const used=rows.filter(p=>p&&p.used&&p.id).map(p=>String(p.id));
      localStorage.setItem(USED_KEY,JSON.stringify(used));
    }catch{}
  }

  function normalize(row){
    return {
      id:String(row.id||''),
      book:String(row.book||''),
      value:Number(row.value||0),
      expires:String(row.expires||''),
      promo:String(row.promo||''),
      kind:String(row.kind||'bonus'),
      estimated:Boolean(row.estimated),
      notes:String(row.notes||''),
      used:Boolean(row.used)
    };
  }

  async function sheetLoad(){
    const configured=await configure();
    if(!configured){
      if(fallbackLoad)return fallbackLoad();
      return false;
    }
    try{
      const data=await bridgeList();
      if(!data||data.ok===false||!Array.isArray(data.promos))throw new Error('Invalid Sheet response');
      const rows=data.promos.map(normalize).filter(p=>p.id&&p.book&&p.expires);
      setUsedStatus(rows);
      promos=rows.filter(p=>!p.used);
      dataUpdatedAt=data.updatedAt||new Date().toISOString();
      dataMode='live';
      try{localStorage.setItem('free-bet-tracker-v10-20260918-slate',JSON.stringify({updatedAt:dataUpdatedAt,promos}))}catch{}
      const strip=document.querySelector('#strip');
      if(strip){strip.className='strip';strip.textContent=''}
      if(typeof render==='function')render();
      return true;
    }catch{
      if(fallbackLoad){
        await fallbackLoad();
        dataMode='snapshot';
        const strip=document.querySelector('#strip');
        if(strip){strip.className='strip show';strip.textContent='Sheet sync is unavailable right now. Showing the backup promo snapshot.'}
        if(typeof render==='function')render();
      }
      return false;
    }
  }

  window.__fbtSheetLoad=sheetLoad;
  try{load=sheetLoad}catch{}
  const refresh=document.querySelector('#refresh');
  if(refresh)refresh.onclick=sheetLoad;
  setTimeout(sheetLoad,120);
  setInterval(sheetLoad,60000);
  window.addEventListener('focus',()=>sheetLoad());
})();
