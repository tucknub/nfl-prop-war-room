export const PLAYER_HEADERS = ['Game', 'Player/Unit', 'Team', 'Markets', 'Strongest Signal', 'Source Count', 'High Confidence', 'Positive', 'Caution', 'Avg Evidence', 'Priority Score', 'Next Check', 'Dashboard?'];
export const EVIDENCE_HEADERS = ['Game', 'Player / Unit', 'Team', 'Source', 'Timestamp', 'Section', 'Intel Type', 'Key Takeaway', 'Markets Affected', 'Direction', 'Confidence', 'Evidence Score', 'Transcript Verified', 'External Verified', 'Action Status', 'Source URL', 'Notes'];
export const SOURCE_HEADERS = ['Source', 'Format', 'Creator', 'Game', 'URL', 'Runtime', 'Transcript Status', 'Evidence Class', 'Date Added', 'Use / Caveat'];
export const TRANSLATION_HEADERS = ['Game', 'Player / Unit', 'Team', 'Market', 'Research Lean', 'Confidence', 'Evidence Score', 'Evidence Summary', 'Pre-Bet Check', 'Workflow', 'Live Book / Price', 'Notes', 'Indep. Sources', 'Priority Score', 'Research Grade', 'Next Action'];

export const CATEGORY_META = {
  ALL: { id: 'ALL', label: 'All', question: 'What are the strongest football-intelligence targets this week?' },
  TD_SCORER: { id: 'TD_SCORER', label: 'TD Scorer', question: 'Who should I be looking at for a touchdown this week, and why?' },
  RECEIVING_YARDS: { id: 'RECEIVING_YARDS', label: 'Receiving Yards', question: 'Who should I be looking at for receiving yards this week, and why?' },
  RECEPTIONS: { id: 'RECEPTIONS', label: 'Receptions', question: 'Who should I be looking at for receptions this week, and why?' },
  RUSHING: { id: 'RUSHING', label: 'Rushing', question: 'Who should I be looking at in the rushing game this week, and why?' },
  PASSING: { id: 'PASSING', label: 'Passing', question: 'Who should I be looking at in the passing game this week, and why?' },
  SACKS_DST: { id: 'SACKS_DST', label: 'Sacks & DST', question: 'Which pass-rush and defensive situations should I be looking at this week, and why?' },
  FADES_UNDERS: { id: 'FADES_UNDERS', label: 'Fades / Unders', question: 'Which football situations have the strongest caution or fade cases this week, and why?' },
};

export const CATEGORY_ORDER = Object.keys(CATEGORY_META);
export const STATUS_ORDER = ['READY', 'WAITING', 'CONFLICTED', 'RESEARCH_ONLY'];
export const SORT_OPTIONS = [
  ['BEST', 'Best Intel Target'],
  ['STRENGTH', 'Research Strength'],
  ['SOURCES', 'Independent Sources'],
  ['FACT_CHECK', 'Fact Check / Verification Completeness'],
  ['KICKOFF', 'Game / Kickoff'],
  ['ENTITY', 'Player / Unit A-Z'],
];

const PLAYER_CATEGORY_IDS = new Set(['TD_SCORER', 'RECEIVING_YARDS', 'RECEPTIONS', 'RUSHING', 'PASSING']);
const UNIT_PATTERN = /\b(pass rush|front four|secondary|defense|offense|offensive line|\bOL\b|run game|backfield|pass catchers|receivers|WR room|RBs|committee|situation|unit|team total|game total)\b/i;
const MATERIAL_BLOCKER_PATTERN = /\b(injur|ankle|hamstring|groin|health|questionable|doubtful|active|inactive|availability|starter|starting five|depth chart|rotation|backfield split|target split|workload|snap share|route share|role projection|goal[- ]line role|red[- ]zone share|personnel|weather)\b/i;
const PRICE_CLAUSE_PATTERN = /\b(sportsbook|price|odds|vig|moneyline|\bspread\b|market consensus|live market|line shopping|implied probability|expected value|\bEV\b|best book|minimum odds|profitab|promo mechanics|pre-bet|becomes a bet)\b/i;

const asNumber = (value) => Number(value) || 0;
const toObject = (row, headers) => Object.fromEntries(headers.map((key, index) => [key, row[index] ?? '']));
const text = (value) => String(value ?? '').trim();
const slug = (value) => text(value).toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
const signalKey = (game, entity) => `${game}|${entity}`;

function stableId(prefix, ...parts) {
  return `${prefix}-${parts.map(slug).filter(Boolean).join('-')}`;
}

function mapRows(rows, headers) {
  return (rows || []).map((row) => toObject(row, headers));
}

function isPlayerEntity(entity, team) {
  if (!entity || team === 'BOTH' || UNIT_PATTERN.test(entity) || /\s(?:vs\.?|\/)\s/i.test(entity)) return false;
  return !/^(seattle seahawks|green bay packers|san francisco 49ers|los angeles rams)$/i.test(entity);
}

function canonicalSourceId(source, url) {
  return stableId('source', url || source);
}

function claimedCategoryIds(marketText) {
  const ids = new Set();
  const parts = text(marketText).split(/[;|]/).map((part) => part.trim()).filter(Boolean);
  for (const part of parts) {
    const lower = part.toLowerCase();
    const isPassing = /pass(?:ing)?\s*(?:yards?|tds?|touchdowns?|attempts?|completions?)|interceptions?|\bqb passing\b/.test(lower);
    const exactScorer = /anytime\s+td|first\s+td|touchdown\s+scorer|td\s+scorer/.test(lower);
    const contextualScorer = /\btds?\b/i.test(part) && /rush|receiv|goal[- ]line|red[- ]zone/.test(lower) && !isPassing;
    if (exactScorer || contextualScorer) ids.add('TD_SCORER');
    if (/receiving\s+yards?|alt\s+receiving|longest\s+reception/.test(lower)) ids.add('RECEIVING_YARDS');
    if (/receptions?|catches|catch\s+volume/.test(lower)) ids.add('RECEPTIONS');
    if (/rush(?:ing)?\s+yards?|rush\s+attempts?|carries|designed\s+(?:qb\s+)?rush|qb\s+rush/.test(lower)) ids.add('RUSHING');
    if (isPassing) ids.add('PASSING');
    if (/sacks?|\bdst\b|pass\s+rush|turnovers?|fumbles?/.test(lower)) ids.add('SACKS_DST');
    if (/unders?|fade|caution/.test(lower)) ids.add('FADES_UNDERS');
  }
  return ids;
}

export function sanitizeFootballOnly(value) {
  const clauses = text(value)
    .replace(/\b(check|compare|confirm|refresh|verify)\s+(?:the\s+)?(?:current\s+)?market,?\s*/gi, '')
    .replace(/,?\s*(?:and\s+)?market inflation\b/gi, '')
    .split(/(?<=[.!?;])\s+|\s*;\s*/)
    .map((clause) => clause.trim())
    .filter(Boolean)
    .filter((clause) => !PRICE_CLAUSE_PATTERN.test(clause))
    .filter((clause) => !/\b(check|compare|confirm|refresh|verify)\b.*\b(line|total)\b/i.test(clause));
  return clauses.join(' ').replace(/^[,.;:\s]+|[,.;:\s]+$/g, '').trim();
}

export function sourceCappedQuality(items) {
  const bestBySource = new Map();
  for (const item of items.filter((entry) => entry.isVideoClaim)) {
    bestBySource.set(item.canonicalSourceId, Math.max(bestBySource.get(item.canonicalSourceId) || 0, asNumber(item['Evidence Score'])));
  }
  if (!bestBySource.size) return 0;
  let total = 0;
  for (const score of bestBySource.values()) total += score;
  return total / bestBySource.size;
}

export function researchStrengthV2(independentSources, items) {
  const sourceComponent = Math.min(asNumber(independentSources), 3) * 2.3;
  const qualityComponent = sourceCappedQuality(items) * 0.75;
  return Math.min(10, Math.max(0, Math.round((((sourceComponent + qualityComponent) / 10.65) * 10) * 10) / 10));
}

export function strengthBand(score) {
  if (score >= 8.5) return 'Exceptional';
  if (score >= 7) return 'Strong';
  if (score >= 5) return 'Developing';
  return 'Thin';
}

export function directionState(items) {
  const values = new Set(items.filter((item) => item.isVideoClaim).map((item) => item.Direction));
  if (values.has('Positive') && (values.has('Negative') || values.has('Caution'))) return 'Mixed';
  if (values.has('Negative')) return 'Negative';
  if (values.has('Caution')) return 'Caution';
  if (values.has('Positive')) return 'Positive';
  return 'Neutral';
}

export function verificationState(items) {
  const videoClaims = items.filter((item) => item.isVideoClaim);
  const values = videoClaims.map((item) => item['External Verified'] || 'Not Checked');
  if (values.includes('Refuted')) return 'CONFLICT';
  if (values.includes('Mixed')) return 'MIXED';
  const high = videoClaims.filter((item) => item.Confidence === 'High' && asNumber(item['Evidence Score']) >= 4);
  const confirmedHigh = high.filter((item) => item['External Verified'] === 'Confirmed').length;
  if (high.length && confirmedHigh === high.length) return 'VERIFIED';
  if (confirmedHigh || values.includes('Confirmed') || items.some((item) => item.isExternalUpdate && item['External Verified'] === 'Confirmed')) return 'PARTIAL';
  return 'UNCHECKED';
}

export function verificationCompleteness(state) {
  return ({ VERIFIED: 4, PARTIAL: 3, UNCHECKED: 2, MIXED: 1, CONFLICT: 0 })[state] ?? 0;
}

function hasIndependentConflict(items) {
  const positive = new Set();
  const negative = new Set();
  for (const item of items.filter((entry) => entry.isVideoClaim)) {
    if (item.Direction === 'Positive') positive.add(item.canonicalSourceId);
    if (item.Direction === 'Negative') negative.add(item.canonicalSourceId);
  }
  if (!positive.size || !negative.size) return false;
  for (const sourceId of positive) if (!negative.has(sourceId) || negative.size > 1) return true;
  return false;
}

function materialBlocker(player, items) {
  const unresolved = `${sanitizeFootballOnly(player['Strongest Signal'])} ${sanitizeFootballOnly(player['Next Check'])}`;
  if (!MATERIAL_BLOCKER_PATTERN.test(unresolved)) return false;
  const related = items.filter((item) => ['Injury', 'Role', 'Personnel'].includes(item['Intel Type']));
  return !related.length || related.some((item) => item['External Verified'] !== 'Confirmed');
}

function uncertaintyTypes(player, items) {
  const content = `${player['Strongest Signal']} ${player['Next Check']} ${items.map((item) => `${item['Intel Type']} ${item['Key Takeaway']}`).join(' ')}`.toLowerCase();
  const result = new Set();
  const rules = {
    Injury: /injur|health|ankle|hamstring|groin|questionable|active|inactive/,
    Role: /role|routes?|red[- ]zone|goal[- ]line/,
    Workload: /workload|volume|snap|attempts?|touches|target share/,
    Personnel: /personnel|offensive line|\bol\b|depth chart|rotation|starter/,
    Assignment: /assignment|alignment|shadow|coverage plan/,
    Weather: /weather|wind|rain|snow/,
    Scheme: /scheme|blitz|two-high|single-high|play action|structure/,
  };
  for (const [name, pattern] of Object.entries(rules)) if (pattern.test(content)) result.add(name);
  return [...result];
}

function evidenceTypes(items) {
  return [...new Set(items.filter((item) => item.isVideoClaim).map((item) => text(item['Intel Type'])).filter(Boolean))];
}

function statusFor(candidate) {
  if (!candidate.categoryIds.length || !candidate.videoEvidence.length) return 'RESEARCH_ONLY';
  if (['CONFLICT', 'MIXED'].includes(candidate.verification) || hasIndependentConflict(candidate.evidence)) return 'CONFLICTED';
  if (materialBlocker(candidate.player, candidate.evidence)) return 'WAITING';
  if (['VERIFIED', 'PARTIAL'].includes(candidate.verification)) return 'READY';
  return 'RESEARCH_ONLY';
}

function cardContent(player, items) {
  const ranked = [...items].sort((a, b) => asNumber(b['Evidence Score']) - asNumber(a['Evidence Score']));
  const positive = ranked.find((item) => item.isVideoClaim && item.Direction === 'Positive');
  const counter = ranked.find((item) => item.isVideoClaim && ['Negative', 'Caution'].includes(item.Direction));
  return {
    bottomLine: sanitizeFootballOnly(player['Strongest Signal']) || 'No bottom-line signal is recorded.',
    why: sanitizeFootballOnly(positive?.['Key Takeaway']) || sanitizeFootballOnly(player['Strongest Signal']) || 'No supporting claim is recorded.',
    counter: sanitizeFootballOnly(counter?.['Key Takeaway']) || 'No material counter-case captured in current evidence.',
    unknown: sanitizeFootballOnly(player['Next Check']) || 'No unresolved football question is recorded.',
  };
}

function sortBand(candidate) {
  if (candidate.status === 'READY') return candidate.independentSources >= 2 ? 0 : 1;
  if (candidate.status === 'WAITING') return candidate.independentSources >= 2 ? 2 : 3;
  if (candidate.status === 'RESEARCH_ONLY') return 4;
  return 5;
}

export function bestIntelCompare(a, b) {
  return sortBand(a) - sortBand(b)
    || b.independentSources - a.independentSources
    || b.researchStrength - a.researchStrength
    || b.verificationCompleteness - a.verificationCompleteness
    || a.kickoff.localeCompare(b.kickoff)
    || a.entity.localeCompare(b.entity);
}

export function sortCandidates(candidates, sortId) {
  const copy = [...candidates];
  return copy.sort((a, b) => {
    if (sortId === 'STRENGTH') return b.researchStrength - a.researchStrength || bestIntelCompare(a, b);
    if (sortId === 'SOURCES') return b.independentSources - a.independentSources || bestIntelCompare(a, b);
    if (sortId === 'FACT_CHECK') return b.verificationCompleteness - a.verificationCompleteness || bestIntelCompare(a, b);
    if (sortId === 'KICKOFF') return a.kickoff.localeCompare(b.kickoff) || a.entity.localeCompare(b.entity);
    if (sortId === 'ENTITY') return a.entity.localeCompare(b.entity) || a.game.localeCompare(b.game);
    return bestIntelCompare(a, b);
  });
}

export function createWeekModel(raw, weekMeta) {
  const players = mapRows(raw.players, PLAYER_HEADERS);
  const evidence = mapRows(raw.video, EVIDENCE_HEADERS);
  const sources = mapRows(raw.sources, SOURCE_HEADERS);
  const translations = mapRows(raw.marketIdeas, TRANSLATION_HEADERS);
  const sourceByName = new Map(sources.map((source) => [source.Source, { ...source, id: canonicalSourceId(source.Source, source.URL), independenceGroup: canonicalSourceId(source.Source, source.URL) }]));
  const evidenceBySignal = new Map();
  const normalizedEvidence = evidence.map((item, index) => {
    const sourceRecord = sourceByName.get(item.Source);
    const isVideoClaim = item['Transcript Verified'] !== 'N/A';
    const normalized = {
      ...item,
      id: stableId('claim', weekMeta.id, item.Game, item['Player / Unit'], item.Source, item.Timestamp, index),
      isVideoClaim,
      isExternalUpdate: !isVideoClaim,
      canonicalSourceId: isVideoClaim ? canonicalSourceId(item.Source, item['Source URL']) : '',
    };
    const key = signalKey(item.Game, item['Player / Unit']);
    const bucket = evidenceBySignal.get(key) || [];
    bucket.push(normalized);
    evidenceBySignal.set(key, bucket);
    return normalized;
  });
  const translationsBySignal = new Map();
  for (const [index, translation] of translations.entries()) {
    const normalized = { ...translation, id: stableId('translation', weekMeta.id, translation.Game, translation['Player / Unit'], translation.Market, index) };
    const key = signalKey(translation.Game, translation['Player / Unit']);
    const bucket = translationsBySignal.get(key) || [];
    bucket.push(normalized);
    translationsBySignal.set(key, bucket);
  }
  const candidates = players.map((player, index) => {
    const key = signalKey(player.Game, player['Player/Unit']);
    const items = evidenceBySignal.get(key) || [];
    const videoEvidence = items.filter((item) => item.isVideoClaim);
    const derivedSourceIds = [...new Set(videoEvidence.map((item) => item.canonicalSourceId))];
    const categoryIds = [...claimedCategoryIds(player.Markets)];
    const direction = directionState(items);
    if (['Negative', 'Caution', 'Mixed'].includes(direction) && !categoryIds.includes('FADES_UNDERS')) categoryIds.push('FADES_UNDERS');
    const verification = verificationState(items);
    const base = {
      id: stableId('candidate', weekMeta.id, player.Game, player['Player/Unit']),
      signalId: stableId('signal', weekMeta.id, player.Game, player['Player/Unit'], index),
      signalKey: key,
      player,
      entity: player['Player/Unit'],
      entityType: isPlayerEntity(player['Player/Unit'], player.Team) ? 'PLAYER' : 'UNIT',
      game: player.Game,
      team: player.Team,
      kickoff: weekMeta.gameDates?.[player.Game] || '9999-12-31T23:59:59Z',
      evidence: items,
      videoEvidence,
      externalUpdates: items.filter((item) => item.isExternalUpdate),
      translations: translationsBySignal.get(key) || [],
      categoryIds,
      direction,
      verification,
      verificationCompleteness: verificationCompleteness(verification),
      independentSourceIds: derivedSourceIds,
      independentSources: derivedSourceIds.length,
      storedIndependentSources: asNumber(player['Source Count']),
      uncertaintyTypes: uncertaintyTypes(player, items),
      evidenceTypes: evidenceTypes(items),
      content: cardContent(player, items),
    };
    return { ...base, researchStrength: researchStrengthV2(base.independentSources, items), status: statusFor(base) };
  });
  const gameSummaries = (raw.games || []).filter((row) => text(row[0]).includes(' @ ')).map((row) => ({
    id: stableId('game', weekMeta.id, row[0]), game: row[0] || '', sources: row[1] || '', pick: row[2] || '', score: row[3] || '', market: row[4] || '',
    thesis: sanitizeFootballOnly(row[5]) || '', attack: sanitizeFootballOnly(row[6]) || '', unknowns: sanitizeFootballOnly(row[7]) || '', recheck: sanitizeFootballOnly(row[8]) || '', notes: sanitizeFootballOnly(row[9]) || '',
    kickoff: weekMeta.gameDates?.[row[0]] || '9999-12-31T23:59:59Z',
  }));
  const sourceRecords = [...sourceByName.values()];
  return {
    meta: weekMeta,
    raw,
    players,
    evidence: normalizedEvidence,
    sources: sourceRecords,
    translations: translations.map((translation, index) => ({ ...translation, id: stableId('translation', weekMeta.id, translation.Game, translation['Player / Unit'], translation.Market, index) })),
    candidates,
    games: gameSummaries,
    indexes: { evidenceBySignal, translationsBySignal, sourceByName },
    counts: {
      games: new Set(players.map((player) => player.Game)).size,
      youtubeSources: sourceRecords.length,
      videoClaims: normalizedEvidence.filter((item) => item.isVideoClaim).length,
      externalUpdates: normalizedEvidence.filter((item) => item.isExternalUpdate).length,
      signals: players.length,
      declaredMultiSourceSignals: players.filter((player) => asNumber(player['Source Count']) >= 2).length,
      multiSourceSignals: candidates.filter((candidate) => candidate.independentSources >= 2).length,
      translations: translations.length,
    },
  };
}

export function candidateMatchesCategory(candidate, categoryId) {
  if (categoryId === 'ALL') return candidate.categoryIds.length > 0;
  if (!candidate.categoryIds.includes(categoryId)) return false;
  if (PLAYER_CATEGORY_IDS.has(categoryId)) return candidate.entityType === 'PLAYER';
  return true;
}

export function searchText(candidate) {
  return [candidate.entity, candidate.game, candidate.team, candidate.player.Markets, candidate.player['Strongest Signal'], ...candidate.evidence.map((item) => `${item.Source} ${item['Key Takeaway']} ${item['Intel Type']}`)].join(' ').toLowerCase();
}

export function categoryLabelFor(candidate, preferredId) {
  if (preferredId !== 'ALL' && candidate.categoryIds.includes(preferredId)) return CATEGORY_META[preferredId].label;
  const first = candidate.categoryIds.find((id) => id !== 'FADES_UNDERS') || candidate.categoryIds[0];
  return CATEGORY_META[first]?.label || 'Football Intel';
}

export function candidateDecisionId(candidate, categoryId = 'ALL') {
  const resolved = categoryId !== 'ALL' && candidate.categoryIds.includes(categoryId)
    ? categoryId
    : (candidate.categoryIds.find((id) => id !== 'FADES_UNDERS') || candidate.categoryIds[0] || 'ALL');
  return `${candidate.id}-${slug(resolved)}`;
}

export function sourceGroups(candidate) {
  const groups = new Map();
  for (const item of candidate.videoEvidence) {
    const current = groups.get(item.canonicalSourceId) || { id: item.canonicalSourceId, source: item.Source, sourceLabels: [], url: item['Source URL'], claims: [] };
    if (!current.sourceLabels.includes(item.Source)) current.sourceLabels.push(item.Source);
    current.source = current.sourceLabels.join(' / ');
    current.claims.push(item);
    groups.set(item.canonicalSourceId, current);
  }
  return [...groups.values()].sort((a, b) => b.claims.length - a.claims.length || a.source.localeCompare(b.source));
}

export function formatStatus(status) {
  return status === 'RESEARCH_ONLY' ? 'RESEARCH ONLY' : status;
}

export function formatVerification(state) {
  return ({ VERIFIED: 'FACT CHECKED', PARTIAL: 'PARTIAL CHECK', UNCHECKED: 'UNCHECKED', MIXED: 'MIXED CHECK', CONFLICT: 'FACT CONFLICT' })[state] || 'UNCHECKED';
}

export function priceBoundaryViolations(value) {
  return text(value).split(/\s+/).filter((token) => PRICE_CLAUSE_PATTERN.test(token));
}

export function exactCategoryIds(value) {
  return [...claimedCategoryIds(value)];
}
