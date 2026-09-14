const SHEET_NAME = 'Free Bets';
const START_ROW = 7;

function doGet(e) {
  const action = String((e && e.parameter && e.parameter.action) || 'list');
  const callback = String((e && e.parameter && e.parameter.callback) || 'callback');
  const payload = action === 'list' ? {promos: listPromos_()} : {ok: false, error: 'Unsupported action'};
  return ContentService.createTextOutput(callback + '(' + JSON.stringify(payload) + ')')
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  const action = String(p.action || '');
  if (action === 'add') addPromo_(p);
  else if (action === 'used') setUsed_(String(p.id || ''), String(p.used) === 'true');
  else if (action === 'delete') deletePromo_(String(p.id || ''));
  return ContentService.createTextOutput(JSON.stringify({ok: true}))
    .setMimeType(ContentService.MimeType.JSON);
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME);
}

function listPromos_() {
  const sh = sheet_();
  const last = Math.max(sh.getLastRow(), START_ROW - 1);
  if (last < START_ROW) return [];
  const rows = sh.getRange(START_ROW, 1, last - START_ROW + 1, 8).getValues();
  return rows.map((r, i) => {
    if (!r[0]) return null;
    const expires = r[2] instanceof Date ? r[2].toISOString() : String(r[2] || '');
    return {id: String(r[7] || 'row-' + (START_ROW + i)), book: String(r[0] || ''), value: Number(r[1] || 0), expires, used: Boolean(r[4]), promo: String(r[5] || ''), notes: String(r[6] || '')};
  }).filter(Boolean);
}

function addPromo_(p) {
  const sh = sheet_();
  const row = Math.max(sh.getLastRow() + 1, START_ROW);
  sh.getRange(row, 1, 1, 8).setValues([[String(p.book || ''), Number(p.value || 0), new Date(p.expires), '', String(p.used) === 'true', String(p.promo || ''), String(p.notes || ''), String(p.id || Utilities.getUuid())]]);
  sh.getRange(row, 4).setFormula(`=IF(OR(A${row}="",E${row}=TRUE,C${row}=""),"",ROUND((C${row}-NOW())*24,1))`);
}

function findRowById_(id) {
  const sh = sheet_();
  const last = sh.getLastRow();
  if (last < START_ROW) return -1;
  const ids = sh.getRange(START_ROW, 8, last - START_ROW + 1, 1).getDisplayValues();
  const idx = ids.findIndex(r => String(r[0]) === id);
  return idx < 0 ? -1 : START_ROW + idx;
}

function setUsed_(id, used) {
  const row = findRowById_(id);
  if (row > 0) sheet_().getRange(row, 5).setValue(Boolean(used));
}

function deletePromo_(id) {
  const row = findRowById_(id);
  if (row > 0) sheet_().deleteRow(row);
}
