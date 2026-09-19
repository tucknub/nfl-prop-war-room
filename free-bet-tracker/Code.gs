const SHEET_NAME = 'Free Bets';
const START_ROW = 7;

function doGet(e) {
  const p = (e && e.parameter) || {};
  const action = String(p.action || 'list');
  const callback = String(p.callback || 'callback').replace(/[^A-Za-z0-9_.$]/g, '') || 'callback';
  let payload;

  if (action === 'list') payload = {ok: true, promos: listUsedStatus_()};
  else if (action === 'ping') payload = {ok: true, service: 'free-bet-tracker', time: new Date().toISOString()};
  else payload = {ok: false, error: 'Unsupported action'};

  return ContentService.createTextOutput(callback + '(' + JSON.stringify(payload) + ')')
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  const action = String(p.action || '');
  const ok = action === 'used'
    ? setUsed_(String(p.id || ''), String(p.used) === 'true')
    : false;

  return ContentService.createTextOutput(JSON.stringify({ok, action}))
    .setMimeType(ContentService.MimeType.JSON);
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('Missing sheet: ' + SHEET_NAME);
  return sh;
}

function listUsedStatus_() {
  const sh = sheet_();
  const last = Math.max(sh.getLastRow(), START_ROW - 1);
  if (last < START_ROW) return [];

  const rows = sh.getRange(START_ROW, 1, last - START_ROW + 1, 8).getValues();
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

  return rows
    .filter(r => r[0] && r[7])
    .map(r => ({id: String(r[7]), used: Boolean(r[4])}));
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
