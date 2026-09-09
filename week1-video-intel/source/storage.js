import { candidateDecisionId } from './dataModel.js';

const STATUS_PRIORITY = { '': 0, Pass: 1, Watch: 2, Shortlist: 3 };

export function storageNamespace(meta) {
  return `nfl-video-intel:v2:${meta.season}:w${meta.week}`;
}

function readJson(storage, key) {
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeJson(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

function mergeDecision(current = {}, incoming = {}) {
  const currentStatus = current.status || '';
  const incomingStatus = incoming.status || '';
  const status = STATUS_PRIORITY[incomingStatus] > STATUS_PRIORITY[currentStatus] ? incomingStatus : currentStatus;
  const notes = [current.note, incoming.note].map((value) => String(value || '').trim()).filter(Boolean);
  return { status, note: [...new Set(notes)].join('\n') };
}

function matchingCandidates(model, game, entity) {
  return model.candidates.filter((candidate) => candidate.game === game && candidate.entity === entity);
}

function migrateLegacyRecord(target, model, legacyKey, value, marketName = '') {
  const parts = legacyKey.split('|');
  if (parts.length < 2) return 0;
  const [game, entity] = parts;
  const candidates = matchingCandidates(model, game, entity);
  if (!candidates.length) return 0;
  const note = value?.note ? `${marketName ? `[${marketName}] ` : ''}${value.note}` : '';
  for (const candidate of candidates) {
    for (const categoryId of candidate.categoryIds) {
      const decisionId = candidateDecisionId(candidate, categoryId);
      target[decisionId] = mergeDecision(target[decisionId], { status: value?.status || '', note });
    }
  }
  return candidates.length;
}

export function loadAndMigrateState(storage, model) {
  const namespace = storageNamespace(model.meta);
  const decisionsKey = `${namespace}:decisions`;
  const migrationKey = `${namespace}:migration`;
  const stored = readJson(storage, decisionsKey);
  const decisions = {};
  let migratedPrototypeKeys = 0;

  const stableDecisionIds = new Set(model.candidates.flatMap((candidate) => candidate.categoryIds.map((categoryId) => candidateDecisionId(candidate, categoryId))));
  for (const [key, value] of Object.entries(stored)) {
    if (stableDecisionIds.has(key)) {
      decisions[key] = mergeDecision(decisions[key], value);
      continue;
    }
    const oldCandidate = model.candidates.find((candidate) => candidate.id === key);
    if (oldCandidate) {
      for (const categoryId of oldCandidate.categoryIds) {
        const decisionId = candidateDecisionId(oldCandidate, categoryId);
        decisions[decisionId] = mergeDecision(decisions[decisionId], value);
      }
      migratedPrototypeKeys += 1;
      continue;
    }
    if (key.includes('|')) migratedPrototypeKeys += migrateLegacyRecord(decisions, model, key, value);
  }

  const report = { version: 2, at: new Date().toISOString(), migratedPrototypeKeys, migratedLegacyRecords: 0, preservedOrphans: 0 };
  if (model.meta.season === 2026 && model.meta.week === 1) {
    const legacySources = [
      ['w1SignalState', false],
      ['w1MarketState', true],
      ['w1IntelState', true],
    ];
    const orphans = {};
    for (const [legacyStorageKey, hasMarket] of legacySources) {
      const legacy = readJson(storage, legacyStorageKey);
      for (const [key, value] of Object.entries(legacy)) {
        const parts = key.split('|');
        const marketName = hasMarket && parts.length > 2 ? parts.slice(2).join('|') : '';
        const migrated = migrateLegacyRecord(decisions, model, key, value, marketName);
        if (migrated) report.migratedLegacyRecords += 1;
        else orphans[`${legacyStorageKey}:${key}`] = value;
      }
    }
    if (Object.keys(orphans).length) {
      report.preservedOrphans = Object.keys(orphans).length;
      writeJson(storage, `${namespace}:legacy-orphans`, orphans);
    }
  }

  writeJson(storage, decisionsKey, decisions);
  writeJson(storage, migrationKey, report);
  return { decisions, report, decisionsKey };
}

export function saveDecisions(storage, meta, decisions) {
  return writeJson(storage, `${storageNamespace(meta)}:decisions`, decisions);
}

export function saveUiPreferences(storage, meta, preferences) {
  return writeJson(storage, `${storageNamespace(meta)}:preferences`, preferences);
}

export function loadUiPreferences(storage, meta) {
  return readJson(storage, `${storageNamespace(meta)}:preferences`);
}
