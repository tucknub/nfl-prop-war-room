import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  CATEGORY_ORDER,
  candidateMatchesCategory,
  createWeekModel,
  exactCategoryIds,
  researchStrengthV2,
  sanitizeFootballOnly,
  sortCandidates,
  sourceGroups,
} from '../source/dataModel.js';

const root = new URL('../', import.meta.url);
const week1Raw = JSON.parse(await readFile(new URL('public/data/2026/week-01.json', root), 'utf8'));
const manifest = JSON.parse(await readFile(new URL('public/data/manifest.json', root), 'utf8'));
const week1Meta = manifest.productionWeeks[0];
const week1 = createWeekModel(week1Raw, week1Meta);
const week2Raw = JSON.parse(await readFile(new URL('fixtures/data/2026/week-02.test.json', root), 'utf8'));
const week2Meta = { id: '2026-w2-fixture', season: 2026, week: 2, label: 'TEST', updated: 'TEST', gameDates: { 'AAA @ BBB': '2026-09-20T13:00:00-04:00', 'CCC @ DDD': '2026-09-20T16:25:00-04:00' } };
const week2 = createWeekModel(week2Raw, week2Meta);

test('Week 1 acceptance counts are preserved exactly', () => {
  assert.deepEqual(week1.counts, { games: 16, youtubeSources: 20, videoClaims: 396, externalUpdates: 4, signals: 210, declaredMultiSourceSignals: 32, multiSourceSignals: 31, translations: 170 });
});

test('all 210 signals retain identity, game, evidence, source counts, strongest signal and category mapping', () => {
  assert.equal(week1.candidates.length, 210);
  for (const candidate of week1.candidates) {
    assert.ok(candidate.entity, `${candidate.signalId}: missing identity`);
    assert.ok(week1.games.some((game) => game.game === candidate.game), `${candidate.entity}: missing game`);
    assert.ok(candidate.videoEvidence.length > 0, `${candidate.entity}: missing video evidence`);
    assert.equal(candidate.player['Strongest Signal'], week1.players.find((player) => player.Game === candidate.game && player['Player/Unit'] === candidate.entity)['Strongest Signal'], `${candidate.entity}: strongest signal drift`);
    assert.ok(candidate.categoryIds.every((categoryId) => CATEGORY_ORDER.includes(categoryId)), `${candidate.entity}: invalid normalized category`);
    assert.ok(candidate.translations.every((translation) => translation.Game === candidate.game && translation['Player / Unit'] === candidate.entity), `${candidate.entity}: translation mapped to the wrong signal`);
    for (const claim of candidate.videoEvidence) {
      assert.ok(claim.Timestamp, `${candidate.entity}: missing evidence timestamp`);
      assert.ok(claim['Source URL'], `${candidate.entity}: missing source URL`);
    }
  }
});

test('all 170 source translations remain available without forcing unsupported signal joins', () => {
  const candidateKeys = new Set(week1.candidates.map((candidate) => `${candidate.game}|${candidate.entity}`));
  const attached = week1.translations.filter((translation) => candidateKeys.has(`${translation.Game}|${translation['Player / Unit']}`));
  const translationOnly = week1.translations.filter((translation) => !candidateKeys.has(`${translation.Game}|${translation['Player / Unit']}`));
  assert.equal(attached.length, 150);
  assert.equal(translationOnly.length, 20);
  assert.equal(attached.length + translationOnly.length, 170);
});

test('Finder excludes support-only signals instead of inventing categories', () => {
  const supportOnly = week1.candidates.filter((candidate) => candidate.categoryIds.length === 0);
  assert.ok(supportOnly.length > 0);
  assert.ok(supportOnly.every((candidate) => !candidateMatchesCategory(candidate, 'ALL')));
});

test('evidence and candidate identities are unique at their intended grain', () => {
  assert.equal(new Set(week1.evidence.map((item) => item.id)).size, week1.evidence.length);
  assert.equal(new Set(week1.candidates.map((item) => item.id)).size, week1.candidates.length);
  assert.equal(new Set(week1.translations.map((item) => item.id)).size, week1.translations.length);
});

test('source convergence uses canonical YouTube sources only', () => {
  const rhamondre = week1.candidates.find((candidate) => candidate.entity === 'Rhamondre Stevenson');
  assert.equal(rhamondre.externalUpdates.length, 1);
  assert.equal(rhamondre.independentSources, 3);
  assert.equal(sourceGroups(rhamondre).length, 3);
  const brown = week1.candidates.find((candidate) => candidate.entity === 'A.J. Brown');
  assert.ok(brown.videoEvidence.length > brown.independentSources);
  assert.equal(sourceGroups(brown).length, brown.independentSources);
  const mismatches = week1.candidates.filter((candidate) => candidate.independentSources !== candidate.storedIndependentSources);
  assert.deepEqual(mismatches.map((candidate) => ({ entity: candidate.entity, game: candidate.game, declared: candidate.storedIndependentSources, canonical: candidate.independentSources })), [
    { entity: 'Green Bay Pass Catchers', game: 'GB @ MIN', declared: 2, canonical: 1 },
  ]);
  const greenBay = mismatches[0];
  assert.equal(greenBay.videoEvidence.length, 2);
  assert.equal(new Set(greenBay.videoEvidence.map((claim) => new URL(claim['Source URL']).searchParams.get('v'))).size, 1);
  const greenBayGroups = sourceGroups(greenBay);
  assert.equal(greenBayGroups.length, 1);
  assert.equal(greenBayGroups[0].claims.length, 2);
  assert.match(greenBayGroups[0].source, /NFL YouTube Game Preview \/ Tom Grossi/);
});

test('Research Strength v2 is direction and verification neutral', () => {
  const positive = [{ isVideoClaim: true, canonicalSourceId: 'one', 'Evidence Score': 5, Direction: 'Positive', 'External Verified': 'Confirmed' }];
  const negative = [{ isVideoClaim: true, canonicalSourceId: 'one', 'Evidence Score': 5, Direction: 'Negative', 'External Verified': 'Refuted' }];
  assert.equal(researchStrengthV2(1, positive), researchStrengthV2(1, negative));
  assert.equal(researchStrengthV2(3, [{ ...positive[0] }, { ...positive[0], canonicalSourceId: 'two', 'Evidence Score': 5 }, { ...positive[0], canonicalSourceId: 'three', 'Evidence Score': 5 }]), 10);
});

test('TD_SCORER taxonomy excludes passing touchdowns and non-player bundles', () => {
  assert.ok(exactCategoryIds('Anytime TD; Receiving Yards').includes('TD_SCORER'));
  assert.ok(!exactCategoryIds('Passing Yards; Passing TDs').includes('TD_SCORER'));
  const tdCandidates = week1.candidates.filter((candidate) => candidateMatchesCategory(candidate, 'TD_SCORER'));
  assert.ok(tdCandidates.length > 0);
  assert.ok(tdCandidates.every((candidate) => candidate.entityType === 'PLAYER'));
  assert.ok(tdCandidates.every((candidate) => !/pass(?:ing)?\s+td/i.test(candidate.player.Markets) || /anytime\s+td/i.test(candidate.player.Markets)));
});

test('Week 2 fixture proves the same model supports categories, negative READY, sorting, games, evidence and source links', () => {
  assert.equal(week2.counts.games, 2);
  assert.equal(week2.counts.videoClaims, 5);
  assert.equal(week2.counts.externalUpdates, 1);
  for (const category of CATEGORY_ORDER) assert.doesNotThrow(() => week2.candidates.filter((candidate) => candidateMatchesCategory(candidate, category)));
  const quarterback = week2.candidates.find((candidate) => candidate.entity === 'Fixture Quarterback');
  assert.equal(quarterback.direction, 'Negative');
  assert.equal(quarterback.status, 'READY');
  assert.ok(quarterback.videoEvidence[0]['Source URL'].startsWith('https://'));
  const sorted = sortCandidates(week2.candidates, 'BEST');
  assert.equal(sorted[0].entity, 'Fixture Receiver');
});

test('football-only presentation sanitizer removes legacy price-oriented clauses', () => {
  const values = [
    'Compare TD price vs market consensus and promo mechanics.',
    'Strong role signal. Check current line and book definition.',
    'No live price = no bet.',
  ];
  for (const value of values) assert.doesNotMatch(sanitizeFootballOnly(value), /price|odds|sportsbook|market consensus|book definition|live market|\bEV\b/i);
});
