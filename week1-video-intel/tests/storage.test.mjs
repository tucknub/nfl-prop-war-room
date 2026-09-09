import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { candidateDecisionId, createWeekModel } from '../source/dataModel.js';
import { loadAndMigrateState, saveDecisions, storageNamespace } from '../source/storage.js';

class MemoryStorage {
  constructor(entries = {}) { this.values = new Map(Object.entries(entries)); }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const root = new URL('../', import.meta.url);
const raw = JSON.parse(await readFile(new URL('fixtures/data/2026/week-02.test.json', root), 'utf8'));
const meta = { id: '2026-w2-fixture', season: 2026, week: 2, label: 'TEST', updated: 'TEST', gameDates: {} };
const model = createWeekModel(raw, meta);

test('week-aware decisions are isolated and use stable category candidate IDs', () => {
  const storage = new MemoryStorage();
  const receiver = model.candidates.find((candidate) => candidate.entity === 'Fixture Receiver');
  const id = candidateDecisionId(receiver, 'TD_SCORER');
  saveDecisions(storage, meta, { [id]: { status: 'Shortlist', note: 'fixture note' } });
  const loaded = loadAndMigrateState(storage, model).decisions;
  assert.deepEqual(loaded[id], { status: 'Shortlist', note: 'fixture note' });
  assert.equal(storage.getItem('nfl-video-intel:v2:2026:w1:decisions'), null);
  assert.equal(storageNamespace(meta), 'nfl-video-intel:v2:2026:w2');
});

test('legacy Week 1 state migrates without deleting original keys', async () => {
  const week1Raw = JSON.parse(await readFile(new URL('public/data/2026/week-01.json', root), 'utf8'));
  const manifest = JSON.parse(await readFile(new URL('public/data/manifest.json', root), 'utf8'));
  const week1 = createWeekModel(week1Raw, manifest.productionWeeks[0]);
  const legacySignal = JSON.stringify({ 'NE @ SEA|A.J. Brown': { status: 'Watch', note: 'legacy signal note' } });
  const legacyMarket = JSON.stringify({ 'NE @ SEA|A.J. Brown|Anytime TD': { status: 'Shortlist', note: 'legacy market note' } });
  const storage = new MemoryStorage({ w1SignalState: legacySignal, w1MarketState: legacyMarket, w1IntelState: '{}' });
  const { decisions, report } = loadAndMigrateState(storage, week1);
  const brown = week1.candidates.find((candidate) => candidate.entity === 'A.J. Brown');
  const id = candidateDecisionId(brown, 'TD_SCORER');
  assert.equal(decisions[id].status, 'Shortlist');
  assert.match(decisions[id].note, /legacy signal note/);
  assert.match(decisions[id].note, /legacy market note/);
  assert.ok(report.migratedLegacyRecords >= 2);
  assert.equal(storage.getItem('w1SignalState'), legacySignal);
  assert.equal(storage.getItem('w1MarketState'), legacyMarket);
});
