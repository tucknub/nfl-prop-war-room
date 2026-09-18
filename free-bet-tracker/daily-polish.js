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
    style.textContent=`
      .attention.upnext{background:linear-gradient(135deg,#261b3b,#5b378b)!important;border-color:rgba(181,140,255,.28)!important}
      .attention.upnext .attentionBang{background:rgba(142,99,255,.2)!important}
      .attention.upnext:after{opacity:.45}
      .firstFlag{display:none!important}
      details.card.first:not(.finalHour):not(.critical) .firstFlag{display:block!important}

      @media (min-width:760px){
        .app{max-width:880px!important;padding-left:24px!important;padding-right:24px!important;padding-bottom:52px!important}
        .hero{padding:24px 24px 22px!important;border-radius:30px!important}
        .top h1{font-size:34px!important;letter-spacing:-.045em!important}
        .top p{font-size:14px!important;margin-top:10px!important}
        .titleBox{padding-left:62px!important;min-height:54px!important}
        .appIcon{width:51px!important;height:51px!important;border-radius:16px!important;top:-3px!important}
        .refresh{width:50px!important;height:50px!important;border-radius:16px!important;font-size:23px!important}
        .liveRow{margin-top:18px!important;font-size:12px!important}
        .logoRail{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))!important;gap:12px!important;margin-top:15px!important}
        .railLogo{height:64px!important;border-radius:17px!important;padding:10px 14px!important}
        .railCount{min-width:21px!important;height:21px!important;font-size:10px!important}
        .railNext{font-size:8px!important;padding:4px 8px!important;bottom:-8px!important}

        .attention{margin:16px 0 18px!important;padding:20px 22px!important;border-radius:24px!important}
        .attentionTop{grid-template-columns:46px minmax(0,1fr) auto!important;gap:14px!important}
        .attentionBang{width:46px!important;height:46px!important;border-radius:15px!important;font-size:27px!important}
        .attentionLabel{font-size:12px!important}
        .attentionPromo{font-size:20px!important}
        .attentionTimer{font-size:31px!important}
        .attentionBottom{margin-top:14px!important;padding-top:13px!important}
        .attentionReason{font-size:13px!important;max-width:76%!important}
        .attentionWhen{font-size:11px!important}

        .summary{grid-template-columns:1.28fr 1fr!important;gap:14px!important;margin:16px 0 12px!important}
        .stat{padding:18px 18px!important;border-radius:21px!important;min-height:126px!important}
        .statMark{width:35px!important;height:35px!important;right:15px!important;top:15px!important;border-radius:11px!important}
        .statMark svg{width:20px!important;height:20px!important}
        .label{font-size:11px!important}
        .num{font-size:34px!important;margin-top:8px!important}
        .statSub{font-size:11px!important;margin-top:6px!important}
        .meta{font-size:12.5px!important;margin:0 4px 28px!important}
        .sectionRow{margin:6px 4px 14px!important}
        .section{font-size:19px!important}
        .section:before{font-size:9px!important;margin-bottom:5px!important}
        .subtle{font-size:12px!important}

        .list{gap:14px!important}
        details.card{border-radius:24px!important}
        summary{padding:20px 20px 17px 24px!important}
        .cardTop{gap:16px!important;align-items:center!important}
        .logoTile{width:68px!important;height:68px!important;flex-basis:68px!important;border-radius:19px!important;padding:9px!important}
        .book{font-size:12px!important}
        .heroValue{font-size:25px!important}
        .promo{font-size:18px!important;margin-top:7px!important}
        .typeLine{margin-top:10px!important}
        .tapHint{font-size:12px!important}
        .typeIcon{width:25px!important;height:25px!important;border-radius:8px!important}
        .foot{margin-top:16px!important;padding-top:13px!important;align-items:center!important}
        .count{font-size:17px!important;min-height:36px!important;padding:7px 12px!important}
        .exact{font-size:12px!important;margin-top:5px!important}
        .pill{font-size:10px!important;padding:7px 10px!important}
        .details{padding:16px 20px 19px 24px!important;font-size:13px!important}
        .detailLabel{font-size:10.5px!important}
        .note{font-size:11.5px!important;margin-top:24px!important}
      }
    `;
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
