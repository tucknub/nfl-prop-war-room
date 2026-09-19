const SHEET_NAME = 'Free Bets';
const START_ROW = 7;

function doGet(e) {
  const p = (e && e.parameter) || {};
  const action = String(p.action || 'list');
  const callback = String(p.callback || 'callback').replace(/[^A-Za-z0-9_.$]/g, '') || 'callback';
  let payload;

  if (action === 'list') payload = {ok: true, promos: listPromos_()};
  else if (action === 'ping') payload = {ok: true, service: 'free-bet-tracker', time: new Date().toISOString()};
  else payload = {ok: false, error: 'Unsupported action'};

  return ContentService.createTextOutput(callback + '(' + JSON.stringify(payload) + ')')
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  const action = String(p.action || '');
  let ok = false;

  if (action === 'add') {
    addPromo_(p);
    ok = true;
  } else if (action === 'used') {
    ok = setUsed_(String(p.id || ''), String(p.used) === 'true');
  } else if (action === 'delete') {
    ok = deletePromo_(String(p.id || ''));
  }

  return ContentService.createTextOutput(JSON.stringify({ok, action}))
    .setMimeType(ContentService.MimeType.JSON);
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('Missing sheet: ' + SHEET_NAME);
  return sh;
}

function listPromos_() {
  const sh = sheet_();
  const last = Math.max(sh.getLastRow(), START_ROW - 1);
  if (last < START_ROW) return [];

  const range = sh.getRange(START_ROW, 1, last - START_ROW + 1, 8);
  const rows = range.getValues();
  let idsChanged = false;

  rows.forEach(r => {
    if (r[0] && !r[7]) {
      r[7] = Utilities.getUuid();
      idsChanged = true;
    }
  });

  if (idsChanged) {
    sh.getRange(START_ROW, 8, rows.length, 1).setValues(rows.map(r => [r[7] || '']));
  }

  return rows.map(r => {
    if (!r[0]) return null;
    const expires = r[2] instanceof Date ? r[2].toISOString() : String(r[2] || '');
    return {
      id: String(r[7] || ''),
      book: String(r[0] || ''),
      value: Number(r[1] || 0),
      expires,
      used: Boolean(r[4]),
      promo: String(r[5] || ''),
      notes: String(r[6] || '')
    };
  }).filter(Boolean);
}

function addPromo_(p) {
  const sh = sheet_();
  const row = Math.max(sh.getLastRow() + 1, START_ROW);
  const expires = p.expiresEpoch ? new Date(Number(p.expiresEpoch)) : new Date(p.expires);

  sh.getRange(row, 1, 1, 8).setValues([[
    String(p.book || ''),
    Number(p.value || 0),
    expires,
    '',
    String(p.used) === 'true',
    String(p.promo || ''),
    String(p.notes || ''),
    String(p.id || Utilities.getUuid())
  ]]);

  sh.getRange(row, 4).setFormula(`=IF(OR(A${row}="",E${row}=TRUE,C${row}=""),"",ROUND((C${row}-NOW())*24,1))`);
}

function findRowById_(id) {
  if (!id) return -1;
  const sh = sheet_();
  const last = sh.getLastRow();
  if (last < START_ROW) return -1;

  const ids = sh.getRange(START_ROW, 8, last - START_ROW + 1, 1).getDisplayValues();
  const idx = ids.findIndex(r => String(r[0]) === id);
  return idx < 0 ? -1 : START_ROW + idx;
}

function setUsed_(id, used) {
  const lock = LockService.getDocumentLock();
  lock.waitLock(5000);
  try {
    const row = findRowById_(id);
    if (row < 0) return false;
    sheet_().getRange(row, 5).setValue(Boolean(used));
    return true;
  } finally {
    lock.releaseLock();
  }
}

function deletePromo_(id) {
  const lock = LockService.getDocumentLock();
  lock.waitLock(5000);
  try {
    const row = findRowById_(id);
    if (row < 0) return false;
    sheet_().deleteRow(row);
    return true;
  } finally {
    lock.releaseLock();
  }
}
