(()=>{
  try {
    [
      'free-bet-tracker-v7',
      'free-bet-tracker-v8',
      'free-bet-tracker-v9-reset-20260918'
    ].forEach(k => localStorage.removeItem(k));
  } catch {}

  setTimeout(() => {
    try {
      if (typeof window.load === 'function') window.load();
      else if (typeof window.render === 'function') window.render();
    } catch {}
  }, 100);
})();
