(()=>{
  try {
    [
      'free-bet-tracker-v7',
      'free-bet-tracker-v8',
      'free-bet-tracker-v9-reset-20260918'
    ].forEach(k => localStorage.removeItem(k));
  } catch {}

  try{
    const style=document.createElement('style');
    style.textContent='.attention.upnext{background:linear-gradient(135deg,#261b3b,#5b378b)!important;border-color:rgba(181,140,255,.28)!important}.attention.upnext .attentionBang{background:rgba(142,99,255,.2)!important}.attention.upnext:after{opacity:.45}.firstFlag{display:none!important}details.card.first:not(.finalHour):not(.critical) .firstFlag{display:block!important}';
    document.head.appendChild(style);
  }catch{}

  function fixFirstFlags(){
    try {
      document.querySelectorAll('.firstFlag').forEach(x=>x.style.display='none');
      const first=document.querySelector('details.card.first:not(.finalHour):not(.critical) .firstFlag');
      if(first) first.style.display='block';
    } catch {}
  }

  try {
    if(typeof priorityLabel==='function'){
      priorityLabel=(p,ms)=>{
        if(ms<=15*60e3)return'EXPIRING NOW';
        if(ms<=60*60e3)return'FINAL HOUR';
        if(p.kind==='bonus'&&ms<=24*60*60e3)return'FREE MONEY AT RISK';
        if(ms<=6*60*60e3)return'DO THIS NEXT';
        if(ms<=24*60*60e3)return'NEEDS ATTENTION TODAY';
        return'UP NEXT';
      };
      priorityTone=ms=>{
        if(ms<=15*60e3)return'critical';
        if(ms<=60*60e3)return'final';
        if(ms<=6*60*60e3)return'hot';
        if(ms<=24*60*60e3)return'warn';
        return'upnext';
      };
      priorityReason=p=>{
        const ms=msLeft(p.expires);
        if(p.kind==='bonus'){
          if(ms<=24*60*60e3)return'You lose '+money(p.value)+' in bonus-bet money if it is not used.';
          return'Your next expiring free or bonus bet. Keep it on the radar before '+exact(p.expires)+'.';
        }
        if(p.kind==='qualifier')return'Use the qualifying offer before this window closes if you want the bonus.';
        if(p.kind==='no_sweat')return ms<=24*60*60e3?'The no-sweat protection disappears when this offer expires.':'Your next expiring protected offer. No action is urgent yet.';
        return ms<=24*60*60e3?'This boost disappears when the timer hits zero.':'Your next expiring promo. No action is urgent yet.';
      };
    }
  } catch {}

  try {
    if(typeof render==='function'){
      const baseRender=render;
      render=function(){baseRender();fixFirstFlags()};
    }
  } catch {}

  setTimeout(()=>{
    try {
      if(typeof render==='function')render();
      fixFirstFlags();
    } catch {}
  },100);
})();
