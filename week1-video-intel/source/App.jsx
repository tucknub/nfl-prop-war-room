import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CATEGORY_META,
  CATEGORY_ORDER,
  SORT_OPTIONS,
  bestIntelCompare,
  candidateDecisionId,
  candidateMatchesCategory,
  categoryLabelFor,
  createWeekModel,
  formatStatus,
  formatVerification,
  sanitizeFootballOnly,
  searchText,
  sortCandidates,
  sourceGroups,
  strengthBand,
} from './dataModel.js';
import { loadAndMigrateState, loadUiPreferences, saveDecisions, saveUiPreferences } from './storage.js';

const TABS = ['Finder', 'Games', 'Intel', 'Evidence', 'Sources'];
const STATUS_OPTIONS = ['ALL', 'READY', 'WAITING', 'CONFLICTED', 'RESEARCH_ONLY'];
const DIRECTIONS = ['ALL', 'Positive', 'Caution', 'Negative', 'Mixed', 'Neutral'];
const FACT_CHECKS = ['ALL', 'VERIFIED', 'PARTIAL', 'UNCHECKED', 'MIXED', 'CONFLICT'];
const SOURCE_FILTERS = ['ANY', '2', '3'];
const DECISIONS = ['ANY', 'Shortlist', 'Watch', 'Pass', 'No decision'];
const ALL = 'ALL';

function Glyph({ children, className = '' }) {
  return <span className={`glyph ${className}`} aria-hidden="true">{children}</span>;
}

function StatusBadge({ status }) {
  const icon = status === 'READY' ? '✓' : status === 'WAITING' ? '◷' : status === 'CONFLICTED' ? '!' : '○';
  return <span className={`status-badge status-${status.toLowerCase().replaceAll('_', '-')}`}><Glyph>{icon}</Glyph>{formatStatus(status)}</span>;
}

function FactBadge({ state }) {
  const icon = state === 'VERIFIED' ? '✓' : state === 'PARTIAL' ? '◐' : state === 'UNCHECKED' ? '?' : '!';
  return <span className={`fact-badge fact-${state.toLowerCase()}`}><Glyph>{icon}</Glyph>{formatVerification(state)}</span>;
}

function SourceBadge({ count }) {
  return <span className={`source-badge ${count >= 2 ? 'converged' : ''}`}><Glyph>◆</Glyph>{count} independent {count === 1 ? 'source' : 'sources'}</span>;
}

function Direction({ value }) {
  const icon = value === 'Positive' ? '↑' : value === 'Negative' ? '↓' : value === 'Mixed' ? '↕' : value === 'Caution' ? '◇' : '→';
  return <span className="direction"><Glyph>{icon}</Glyph><span><strong>{value}</strong><small>Direction</small></span></span>;
}

function ResearchStrength({ score, compact = false }) {
  return <span className={`research-strength ${compact ? 'compact' : ''}`} title="Football research strength only. Not probability or betting value.">
    <strong>{strengthBand(score)}</strong><span>{score.toFixed(1)} / 10</span><small>Research Strength</small>
  </span>;
}

function Header({ tab, onTab, weeks, activeWeekId, onWeek }) {
  return <header className="app-header">
    <div className="brand"><span className="shield" aria-hidden="true">◇</span><div><strong>NFL Video Intel</strong><span>Football evidence from film, signals and sources</span></div></div>
    <nav aria-label="Primary navigation">{TABS.map((item) => <button type="button" key={item} aria-current={tab === item ? 'page' : undefined} className={tab === item ? 'active' : ''} onClick={() => onTab(item)}>{item}</button>)}</nav>
    <div className="header-meta">
      <label className="week-select"><span className="sr-only">NFL week</span><select value={activeWeekId} onChange={(event) => onWeek(event.target.value)}>{weeks.map((week) => <option key={week.id} value={week.id}>{week.label}</option>)}</select><Glyph>⌄</Glyph></label>
      <span className="freshness"><i />Updated {weeks.find((week) => week.id === activeWeekId)?.updated}</span>
      <span className="boundary">Football intelligence only<br />No odds or prices</span>
    </div>
  </header>;
}

function CategoryRail({ categoryId, onCategory, label = 'Football categories' }) {
  return <div className="category-rail" role="tablist" aria-label={label}>
    {CATEGORY_ORDER.map((id, index) => <span className={id === 'FADES_UNDERS' ? 'category-split' : ''} key={id}>
      {id === 'FADES_UNDERS' && <i aria-hidden="true" />}
      <button type="button" role="tab" aria-selected={categoryId === id} tabIndex={categoryId === id ? 0 : -1} className={categoryId === id ? 'active' : ''} onKeyDown={(event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + CATEGORY_ORDER.length) % CATEGORY_ORDER.length;
        onCategory(CATEGORY_ORDER[next]);
      }} onClick={() => onCategory(id)}>{CATEGORY_META[id].label}</button>
    </span>)}
  </div>;
}

function SelectControl({ label, value, onChange, children, className = '' }) {
  return <label className={`select-control ${className}`}><span className="sr-only">{label}</span><select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>{children}</select><Glyph>⌄</Glyph></label>;
}

function MoreFilters({ filters, setFilter, options, onClose }) {
  return <div className="more-filter-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="more-filters" role="dialog" aria-label="More filters">
      <div className="more-filter-head"><strong>More filters</strong><button type="button" onClick={onClose} aria-label="Close more filters">×</button></div>
      <label>Direction<select value={filters.direction} onChange={(event) => setFilter('direction', event.target.value)}>{DIRECTIONS.map((value) => <option value={value} key={value}>{value === ALL ? 'Any direction' : value}</option>)}</select></label>
      <label>Team<select value={filters.team} onChange={(event) => setFilter('team', event.target.value)}><option value={ALL}>Any team</option>{options.teams.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Independent sources<select value={filters.sources} onChange={(event) => setFilter('sources', event.target.value)}>{SOURCE_FILTERS.map((value) => <option value={value} key={value}>{value === 'ANY' ? 'Any' : `${value}+`}</option>)}</select></label>
      <label>External fact check<select value={filters.factCheck} onChange={(event) => setFilter('factCheck', event.target.value)}>{FACT_CHECKS.map((value) => <option value={value} key={value}>{value === ALL ? 'Any fact check' : formatVerification(value)}</option>)}</select></label>
      <label>Uncertainty type<select value={filters.uncertainty} onChange={(event) => setFilter('uncertainty', event.target.value)}><option value={ALL}>Any uncertainty</option>{options.uncertainties.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>User decision<select value={filters.decision} onChange={(event) => setFilter('decision', event.target.value)}>{DECISIONS.map((value) => <option value={value} key={value}>{value === 'ANY' ? 'Any decision' : value}</option>)}</select></label>
      <label>Evidence type<select value={filters.evidenceType} onChange={(event) => setFilter('evidenceType', event.target.value)}><option value={ALL}>Any evidence type</option>{options.evidenceTypes.map((value) => <option key={value}>{value}</option>)}</select></label>
      <button type="button" className="apply-filter" onClick={onClose}>View results</button>
    </section>
  </div>;
}

function ActiveFilters({ filters, clearFilter, clearAll }) {
  const labels = [];
  if (filters.query) labels.push(['query', `Search: ${filters.query}`]);
  if (filters.game !== ALL) labels.push(['game', filters.game]);
  if (filters.status !== ALL) labels.push(['status', formatStatus(filters.status)]);
  if (filters.direction !== ALL) labels.push(['direction', filters.direction]);
  if (filters.team !== ALL) labels.push(['team', filters.team]);
  if (filters.sources !== 'ANY') labels.push(['sources', `${filters.sources}+ sources`]);
  if (filters.factCheck !== ALL) labels.push(['factCheck', formatVerification(filters.factCheck)]);
  if (filters.uncertainty !== ALL) labels.push(['uncertainty', filters.uncertainty]);
  if (filters.decision !== 'ANY') labels.push(['decision', filters.decision]);
  if (filters.evidenceType !== ALL) labels.push(['evidenceType', filters.evidenceType]);
  if (!labels.length) return null;
  return <div className="active-filters" aria-label="Active filters">{labels.map(([key, label]) => <button type="button" key={key} onClick={() => clearFilter(key)}>{label}<span aria-hidden="true">×</span><span className="sr-only">Remove {label} filter</span></button>)}<button type="button" className="clear-all" onClick={clearAll}>Clear all</button></div>;
}

function CandidateCard({ candidate, rank, categoryId, decision, onDecision, onOpen }) {
  const exactCategory = categoryLabelFor(candidate, categoryId);
  return <article className={`candidate-card state-${candidate.status.toLowerCase().replaceAll('_', '-')} ${decision?.status === 'Pass' ? 'user-pass' : ''}`}>
    <div className="candidate-head">
      <span className="rank">#{rank}</span>
      <div className="identity"><h2>{candidate.entity}</h2><p>{candidate.team} · {candidate.game}</p></div>
      <StatusBadge status={candidate.status} />
      <span className="category-tag">{exactCategory}</span>
      <Direction value={candidate.direction} />
      <ResearchStrength score={candidate.researchStrength} compact />
    </div>
    <div className="bottom-line"><span>Bottom line</span><strong>{candidate.content.bottomLine}</strong></div>
    <div className="reason-grid"><div><span>Why we like it</span><p>{candidate.content.why}</p></div><div><span>Main counter-case</span><p>{candidate.content.counter}</p></div><div><span>Biggest unresolved question</span><p>{candidate.content.unknown}</p></div></div>
    <div className="candidate-footer"><div className="metadata"><SourceBadge count={candidate.independentSources} /><FactBadge state={candidate.verification} /></div><div className="card-actions"><button type="button" className={`decision-button ${decision?.status === 'Shortlist' ? 'selected' : ''}`} onClick={() => onDecision(candidate, decision?.status === 'Shortlist' ? '' : 'Shortlist')}><Glyph>♧</Glyph>Shortlist</button><button type="button" className="evidence-button" onClick={(event) => onOpen(candidate, event.currentTarget)}>View Evidence <Glyph>→</Glyph></button></div></div>
  </article>;
}

function EvidenceDrawer({ candidate, categoryId, decision, onDecision, onNote, onClose, origin }) {
  const drawerRef = useRef(null);
  const closeRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const groups = sourceGroups(candidate);
  const factChecked = candidate.evidence.filter((item) => item.isExternalUpdate || item['External Verified'] !== 'Not Checked');
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return; }
      if (event.key !== 'Tab' || !drawerRef.current) return;
      const focusable = [...drawerRef.current.querySelectorAll('button, a[href], textarea, input, select, [tabindex]:not([tabindex="-1"])')].filter((element) => !element.disabled);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', onKeyDown); origin?.focus(); };
  }, [origin]);
  return <div className="drawer-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside ref={drawerRef} className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <button ref={closeRef} type="button" className="drawer-close" aria-label="Close evidence" onClick={onClose}>×</button>
      <div className="drawer-header"><div><span className="eyebrow">{categoryLabelFor(candidate, categoryId)} · {candidate.game}</span><h2 id="drawer-title">{candidate.entity}</h2><p>{candidate.team} · {candidate.direction} football direction</p></div><StatusBadge status={candidate.status} /></div>
      <div className="drawer-decisions" aria-label="Your decision">{['Shortlist', 'Watch', 'Pass'].map((value) => <button type="button" key={value} className={decision?.status === value ? `selected ${value.toLowerCase()}` : ''} onClick={() => onDecision(candidate, decision?.status === value ? '' : value)}>{value}</button>)}</div>
      <div className="drawer-kpis"><ResearchStrength score={candidate.researchStrength} /><div><strong>{candidate.independentSources}</strong><span>Independent YouTube sources</span></div><div><strong>{formatVerification(candidate.verification)}</strong><span>External fact-check state</span></div></div>
      <section className="drawer-summary"><div><h3>Why we like it</h3><p>{candidate.content.why}</p></div><div><h3>What could kill it</h3><p>{candidate.content.counter}</p></div><div><h3>What is still unknown</h3><p>{candidate.content.unknown}</p></div></section>
      <section className="convergence-panel"><Glyph>◆</Glyph><div><h3>Source convergence</h3><p>{candidate.independentSources} canonical YouTube {candidate.independentSources === 1 ? 'source supports' : 'sources support'} this signal. Repeated claims from one video stay grouped below and count once. External verification never counts toward convergence.</p></div></section>
      {factChecked.length > 0 && <section className="fact-check-panel"><div className="section-title"><h3>Current factual checks</h3><span>Does not count toward convergence</span></div>{factChecked.map((item) => <div className="fact-row" key={`fact-${item.id}`}><FactBadge state={item['External Verified'] === 'Confirmed' ? 'VERIFIED' : item['External Verified'] === 'Mixed' ? 'MIXED' : item['External Verified'] === 'Refuted' ? 'CONFLICT' : 'UNCHECKED'} /><p>{sanitizeFootballOnly(item['Key Takeaway']) || 'No football-only verification text is recorded.'}</p>{item.isExternalUpdate && item['Source URL'] && <a href={item['Source URL']} target="_blank" rel="noreferrer">Open current source →</a>}</div>)}</section>}
      <section className="evidence-stack"><div className="section-title"><h3>Full evidence stack</h3><span>{candidate.videoEvidence.length} video claims · {groups.length} independent {groups.length === 1 ? 'source' : 'sources'}</span></div>{groups.map((group) => <article className="source-group" key={group.id}><div className="source-group-head"><div><strong>{group.source}</strong><span>{group.claims.length} {group.claims.length === 1 ? 'claim' : 'claims'} from this source · counts as 1 independent source</span></div>{group.url && <a href={group.url} target="_blank" rel="noreferrer">Open source →</a>}</div>{group.claims.map((item) => <div className="claim" key={item.id}><div className="claim-meta"><a href={item['Source URL']} target="_blank" rel="noreferrer">{item.Timestamp || 'No timestamp'}</a><span>{item['Intel Type']}</span><span>{item.Direction}</span><span>{item.Confidence} confidence</span></div><p>{sanitizeFootballOnly(item['Key Takeaway']) || 'No football takeaway is recorded.'}</p>{sanitizeFootballOnly(item.Notes) && <small>{sanitizeFootballOnly(item.Notes)}</small>}</div>)}</article>)}</section>
      <section className="notes-panel"><h3>Your notes</h3><label><span className="sr-only">Notes for {candidate.entity}</span><textarea value={decision?.note || ''} onChange={(event) => onNote(candidate, event.target.value)} placeholder="Add your own note about this football signal..." /></label></section>
    </aside>
  </div>;
}

const DEFAULT_FILTERS = { query: '', game: ALL, status: ALL, direction: ALL, team: ALL, sources: 'ANY', factCheck: ALL, uncertainty: ALL, decision: 'ANY', evidenceType: ALL };

function Finder({ model, categoryId, onCategory, decisions, updateDecision }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sortId, setSortId] = useState('BEST');
  const [moreOpen, setMoreOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(12);
  const [drawer, setDrawer] = useState(null);
  const setFilter = (key, value) => { setFilters((current) => ({ ...current, [key]: value })); setVisibleCount(12); };
  const options = useMemo(() => ({
    teams: [...new Set(model.candidates.map((candidate) => candidate.team).filter((team) => team && team !== 'BOTH'))].sort(),
    uncertainties: [...new Set(model.candidates.flatMap((candidate) => candidate.uncertaintyTypes))].sort(),
    evidenceTypes: [...new Set(model.candidates.flatMap((candidate) => candidate.evidenceTypes))].sort(),
  }), [model]);
  const results = useMemo(() => {
    const query = filters.query.trim().toLowerCase();
    const filtered = model.candidates.filter((candidate) => {
      const decisionId = candidateDecisionId(candidate, categoryId);
      const decision = decisions[decisionId]?.status || '';
      return candidateMatchesCategory(candidate, categoryId)
        && (!query || searchText(candidate).includes(query))
        && (filters.game === ALL || candidate.game === filters.game)
        && (filters.status === ALL || candidate.status === filters.status)
        && (filters.direction === ALL || candidate.direction === filters.direction)
        && (filters.team === ALL || candidate.team === filters.team)
        && (filters.sources === 'ANY' || candidate.independentSources >= Number(filters.sources))
        && (filters.factCheck === ALL || candidate.verification === filters.factCheck)
        && (filters.uncertainty === ALL || candidate.uncertaintyTypes.includes(filters.uncertainty))
        && (filters.decision === 'ANY' || (filters.decision === 'No decision' ? !decision : decision === filters.decision))
        && (filters.evidenceType === ALL || candidate.evidenceTypes.includes(filters.evidenceType));
    });
    return sortCandidates(filtered, sortId);
  }, [model, categoryId, decisions, filters, sortId]);
  const clearFilter = (key) => setFilter(key, key === 'query' ? '' : key === 'sources' || key === 'decision' ? (key === 'sources' ? 'ANY' : 'ANY') : ALL);
  const clearAll = () => { setFilters(DEFAULT_FILTERS); setVisibleCount(12); };
  const extraCount = ['direction', 'team', 'sources', 'factCheck', 'uncertainty', 'decision', 'evidenceType'].filter((key) => filters[key] !== DEFAULT_FILTERS[key]).length;
  return <main className="page-shell">
    <section className="finder-intro"><span className="eyebrow">Finder</span><h1>{CATEGORY_META[categoryId].question}</h1><p>Real football evidence. Clear reasoning. Full provenance when you need it.</p></section>
    <CategoryRail categoryId={categoryId} onCategory={onCategory} />
    <div className="filter-bar">
      <label className="search-control"><Glyph>⌕</Glyph><span className="sr-only">Search</span><input value={filters.query} onChange={(event) => setFilter('query', event.target.value)} placeholder="Search players, teams, games, or football concepts..." /></label>
      <SelectControl label="Game" value={filters.game} onChange={(value) => setFilter('game', value)}><option value={ALL}>All games</option>{model.games.map((game) => <option key={game.id} value={game.game}>{game.game}</option>)}</SelectControl>
      <SelectControl label="System status" value={filters.status} onChange={(value) => setFilter('status', value)}>{STATUS_OPTIONS.map((value) => <option value={value} key={value}>{value === ALL ? 'All statuses' : formatStatus(value)}</option>)}</SelectControl>
      <SelectControl label="Sort" value={sortId} onChange={setSortId} className="sort-control">{SORT_OPTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</SelectControl>
      <button type="button" className={`more-button ${moreOpen ? 'active' : ''}`} onClick={() => setMoreOpen((open) => !open)}><Glyph>☷</Glyph>More filters{extraCount > 0 && <span>{extraCount}</span>}</button>
    </div>
    {moreOpen && <MoreFilters filters={filters} setFilter={setFilter} options={options} onClose={() => setMoreOpen(false)} />}
    <ActiveFilters filters={filters} clearFilter={clearFilter} clearAll={clearAll} />
    <div className="result-summary" aria-live="polite"><span>Showing <strong>{Math.min(visibleCount, results.length)}</strong> of <strong>{results.length}</strong> {CATEGORY_META[categoryId].label} candidates</span><div>{results.some((candidate) => candidate.status === 'CONFLICTED') && <span className="conflict-count">! {results.filter((candidate) => candidate.status === 'CONFLICTED').length} conflicted</span>}<span>Updated {model.meta.updated}</span></div></div>
    {results.length > 0 ? <div className="candidate-grid">{results.slice(0, visibleCount).map((candidate, index) => { const decisionId = candidateDecisionId(candidate, categoryId); return <CandidateCard key={`${candidate.id}-${categoryId}`} candidate={candidate} rank={index + 1} categoryId={categoryId} decision={decisions[decisionId]} onDecision={(target, status) => updateDecision(target, categoryId, { status })} onOpen={(target, origin) => setDrawer({ candidate: target, origin })} />; })}</div> : <div className="empty-state"><Glyph>⌕</Glyph><h2>No candidates match these filters</h2><p>Clear one or more filters to return to the weekly board.</p><button type="button" onClick={clearAll}>Clear filters</button></div>}
    {visibleCount < results.length && <button type="button" className="show-more" onClick={() => setVisibleCount((count) => count + 12)}>Show 12 more</button>}
    {drawer && <EvidenceDrawer candidate={drawer.candidate} categoryId={categoryId} decision={decisions[candidateDecisionId(drawer.candidate, categoryId)]} origin={drawer.origin} onClose={() => setDrawer(null)} onDecision={(target, status) => updateDecision(target, categoryId, { status })} onNote={(target, note) => updateDecision(target, categoryId, { note })} />}
  </main>;
}

function GamesView({ model, categoryId, onCategory, decisions, updateDecision }) {
  const [drawer, setDrawer] = useState(null);
  const matchingGames = model.games.map((game) => ({ ...game, candidates: model.candidates.filter((candidate) => candidate.game === game.game && candidateMatchesCategory(candidate, categoryId)).sort(bestIntelCompare).slice(0, 4) })).filter((game) => categoryId === ALL || game.candidates.length > 0);
  const isFiltered = categoryId !== ALL;
  return <main className="page-shell"><section className="finder-intro"><span className="eyebrow">Games</span><h1>See the weekly slate through each game</h1><p>Game context first, then the strongest matching football-intel signals.</p></section><CategoryRail categoryId={categoryId} onCategory={onCategory} label="Game football categories" /><div className="game-grid">{matchingGames.map((game, gameIndex) => <article className="game-card" key={game.id}><div className="game-card-head"><div><span>{isFiltered ? `${gameIndex + 1} of ${matchingGames.length} matching · ${model.counts.games} total games` : `Game ${gameIndex + 1} of ${model.counts.games}`}</span><h2>{game.game}</h2></div><SourceBadge count={model.sources.filter((source) => source.Game === game.game).length} /></div><p className="game-thesis">{game.thesis || 'No football-only game thesis is recorded.'}</p><div className="game-unknown"><Glyph>!</Glyph><div><strong>Biggest unresolved game questions</strong><p>{game.unknowns || 'No unresolved football question is recorded.'}</p></div></div><div className="game-candidates">{game.candidates.length > 0 ? game.candidates.map((candidate, index) => <button type="button" key={candidate.id} onClick={(event) => setDrawer({ candidate, origin: event.currentTarget })}><span className="mini-rank">#{index + 1}</span><span className="mini-name"><strong>{candidate.entity}</strong><small>{candidate.content.bottomLine}</small></span><StatusBadge status={candidate.status} /><ResearchStrength score={candidate.researchStrength} compact /><Glyph>→</Glyph></button>) : <p className="empty-message">No translated candidates for this game.</p>}</div></article>)}</div>{drawer && <EvidenceDrawer candidate={drawer.candidate} categoryId={categoryId} decision={decisions[candidateDecisionId(drawer.candidate, categoryId)]} origin={drawer.origin} onClose={() => setDrawer(null)} onDecision={(target, status) => updateDecision(target, categoryId, { status })} onNote={(target, note) => updateDecision(target, categoryId, { note })} />}</main>;
}

function IntelView({ model }) {
  const [subview, setSubview] = useState('SIGNALS');
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const signals = model.candidates.filter((candidate) => !q || searchText(candidate).includes(q)).sort(bestIntelCompare);
  const translations = model.translations.filter((item) => !q || Object.values(item).join(' ').toLowerCase().includes(q));
  return <main className="page-shell secondary-page"><section className="finder-intro"><span className="eyebrow">Intel</span><h1>Complete football-signal ledger</h1><p>{model.counts.signals} signals and {model.counts.translations} category translations preserved from production.</p></section><div className="subtabs" role="tablist" aria-label="Intel views"><button type="button" role="tab" aria-selected={subview === 'SIGNALS'} className={subview === 'SIGNALS' ? 'active' : ''} onClick={() => setSubview('SIGNALS')}>Signals · {model.counts.signals}</button><button type="button" role="tab" aria-selected={subview === 'TRANSLATIONS'} className={subview === 'TRANSLATIONS' ? 'active' : ''} onClick={() => setSubview('TRANSLATIONS')}>Category translations · {model.counts.translations}</button></div><label className="search-control standalone"><Glyph>⌕</Glyph><span className="sr-only">Search Intel</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search all signals and translations..." /></label>{subview === 'SIGNALS' ? <div className="simple-list">{signals.map((candidate) => <article key={candidate.id}><StatusBadge status={candidate.status} /><div><strong>{candidate.entity}</strong><span>{candidate.game} · {candidate.team}</span><p>{candidate.content.bottomLine}</p></div><SourceBadge count={candidate.independentSources} /><ResearchStrength score={candidate.researchStrength} compact /></article>)}</div> : <div className="translation-list">{translations.map((item) => <article key={item.id}><div><strong>{item['Player / Unit']}</strong><span>{item.Game} · {item.Team}</span></div><span className="category-tag">{sanitizeFootballOnly(item.Market) || 'Football category'}</span><p><strong>{sanitizeFootballOnly(item['Research Lean'])}</strong> {sanitizeFootballOnly(item['Evidence Summary'])}</p></article>)}</div>}</main>;
}

function EvidenceView({ model }) {
  const [subview, setSubview] = useState('VIDEO');
  const [query, setQuery] = useState('');
  const source = subview === 'VIDEO' ? model.evidence.filter((item) => item.isVideoClaim) : model.evidence.filter((item) => item.isExternalUpdate);
  const q = query.trim().toLowerCase();
  const rows = source.filter((item) => !q || Object.values(item).join(' ').toLowerCase().includes(q));
  return <main className="page-shell secondary-page"><section className="finder-intro"><span className="eyebrow">Evidence</span><h1>Evidence and current factual checks</h1><p>Every production row stays traceable to its source and timestamp.</p></section><div className="subtabs" role="tablist" aria-label="Evidence views"><button type="button" role="tab" aria-selected={subview === 'VIDEO'} className={subview === 'VIDEO' ? 'active' : ''} onClick={() => setSubview('VIDEO')}>Video claims · {model.counts.videoClaims}</button><button type="button" role="tab" aria-selected={subview === 'EXTERNAL'} className={subview === 'EXTERNAL' ? 'active' : ''} onClick={() => setSubview('EXTERNAL')}>External / current · {model.counts.externalUpdates}</button></div>{subview === 'EXTERNAL' && <div className="external-notice">External/current rows verify football facts. They never count as independent YouTube sources.</div>}<label className="search-control standalone"><Glyph>⌕</Glyph><span className="sr-only">Search evidence</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search claims, players, games, or sources..." /></label><div className={`evidence-list ${subview === 'EXTERNAL' ? 'external' : ''}`}>{rows.map((item) => <article key={item.id}><div><strong>{item['Player / Unit']}</strong><span>{item.Game} · {item.Source} · {item.Timestamp}</span></div><p>{sanitizeFootballOnly(item['Key Takeaway']) || 'No football-only claim text is available.'}</p><div className="claim-meta"><span>{item.Direction}</span><span>{item.Confidence} confidence</span><span>Evidence {item['Evidence Score']}</span>{item['Source URL'] && <a href={item['Source URL']} target="_blank" rel="noreferrer">Open source →</a>}</div></article>)}</div></main>;
}

function SourcesView({ model }) {
  return <main className="page-shell secondary-page"><section className="finder-intro"><span className="eyebrow">Sources</span><h1>Canonical YouTube source log</h1><p>{model.counts.youtubeSources} independent source records. Multiple timestamps from one canonical source count once.</p></section><div className="sources-grid">{model.sources.map((source) => <article key={source.id}><span>{source['Evidence Class']}</span><h2>{source.Source}</h2><p>{source.Creator}</p><dl><div><dt>Game</dt><dd>{source.Game}</dd></div><div><dt>Runtime</dt><dd>{source.Runtime}</dd></div><div><dt>Transcript</dt><dd>{source['Transcript Status']}</dd></div></dl><p>{sanitizeFootballOnly(source['Use / Caveat']) || 'No football-only caveat is recorded.'}</p>{source.URL && <a href={source.URL} target="_blank" rel="noreferrer">Open source →</a>}</article>)}</div><a className="sheet-link" href="https://docs.google.com/spreadsheets/d/1N6XCtKkILiJgv5aiqBJx58oI3XN_HNgKSlVD7b5awNs/edit" target="_blank" rel="noreferrer">Open source Google Sheet →</a></main>;
}

function LoadedApp({ model, weeks, activeWeekId, onWeek }) {
  const preferences = useMemo(() => loadUiPreferences(localStorage, model.meta), [model]);
  const [tab, setTab] = useState(() => {
    const hash = location.hash.replace('#', '').toLowerCase();
    return TABS.find((item) => item.toLowerCase() === hash) || 'Finder';
  });
  const [categoryId, setCategoryId] = useState(() => CATEGORY_META[preferences.categoryId] ? preferences.categoryId : 'TD_SCORER');
  const [decisions, setDecisions] = useState(() => loadAndMigrateState(localStorage, model).decisions);
  const onTab = (next) => { setTab(next); history.replaceState(null, '', `#${next.toLowerCase()}`); };
  const onCategory = (next) => { setCategoryId(next); saveUiPreferences(localStorage, model.meta, { categoryId: next }); };
  const updateDecision = (candidate, category, patch) => {
    const key = candidateDecisionId(candidate, category);
    setDecisions((current) => {
      const next = { ...current, [key]: { ...(current[key] || {}), ...patch } };
      saveDecisions(localStorage, model.meta, next);
      return next;
    });
  };
  return <div className="app"><Header tab={tab} onTab={onTab} weeks={weeks} activeWeekId={activeWeekId} onWeek={onWeek} />{model.meta.fixture && <div className="fixture-banner" role="status">NON-PRODUCTION TEST FIXTURE · Invented football content for schema and interaction testing only.</div>}{tab === 'Finder' && <Finder model={model} categoryId={categoryId} onCategory={onCategory} decisions={decisions} updateDecision={updateDecision} />}{tab === 'Games' && <GamesView model={model} categoryId={categoryId} onCategory={onCategory} decisions={decisions} updateDecision={updateDecision} />}{tab === 'Intel' && <IntelView model={model} />}{tab === 'Evidence' && <EvidenceView model={model} />}{tab === 'Sources' && <SourcesView model={model} />}</div>;
}

async function defaultLoader(entry) {
  const response = await fetch(new URL(entry.path, document.baseURI));
  if (!response.ok) throw new Error(`Week package failed to load (${response.status})`);
  return response.json();
}

export function App({ weekEntries = null, loader = defaultLoader }) {
  const [weeks, setWeeks] = useState(weekEntries || []);
  const [activeWeekId, setActiveWeekId] = useState(weekEntries?.[0]?.id || '');
  const [model, setModel] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (weekEntries) return;
    fetch(new URL('data/manifest.json', document.baseURI)).then((response) => {
      if (!response.ok) throw new Error(`Manifest failed to load (${response.status})`);
      return response.json();
    }).then((manifest) => { setWeeks(manifest.productionWeeks); setActiveWeekId(manifest.productionWeeks[0]?.id || ''); }).catch((reason) => setError(reason.message));
  }, [weekEntries]);
  useEffect(() => {
    const entry = weeks.find((week) => week.id === activeWeekId);
    if (!entry) return;
    let cancelled = false;
    setModel(null);
    setError('');
    loader(entry).then((raw) => { if (!cancelled) setModel(createWeekModel(raw, entry)); }).catch((reason) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [weeks, activeWeekId, loader]);
  if (error) return <main className="load-state"><h1>NFL Video Intel</h1><p role="alert">{error}</p></main>;
  if (!model) return <main className="load-state"><h1>NFL Video Intel</h1><p>Loading football research…</p></main>;
  return <LoadedApp key={model.meta.id} model={model} weeks={weeks} activeWeekId={activeWeekId} onWeek={setActiveWeekId} />;
}
