"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRightIcon,
  MinusIcon,
  ReportsIcon,
  StatusIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "@/components/icons";
import type {
  CurrentEvidenceRow,
  MovementEvidenceRow,
  ParsedReportQuery,
  PublishedCurrentReportFixture,
  PublishedMovementReportFixture,
  ReportSort,
} from "@/lib/report-types";

type PublishedReport =
  | PublishedCurrentReportFixture
  | PublishedMovementReportFixture;
type ResultRow = CurrentEvidenceRow | MovementEvidenceRow;

const reportLinks = [
  {
    family: "backfield_control",
    label: "Backfield Control",
    href: "/reports/backfield",
  },
  {
    family: "target_hierarchy",
    label: "Target Hierarchy",
    href: "/reports/targets",
  },
  {
    family: "role_movement",
    label: "Role Movement",
    href: "/reports/movement",
  },
] as const;

const qualityLabels = {
  complete: "Complete",
  reviewed_partial_game: "Reviewed partial game",
  unavailable_supporting_context: "Supporting context unavailable",
} as const;

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const points = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

function sortRows(rows: readonly ResultRow[], sort: ReportSort) {
  const sorted = [...rows];

  if (sort === "authority") {
    return sorted.sort(
      (a, b) => a.authoritativeRank - b.authoritativeRank,
    );
  }

  if (sort === "player") {
    return sorted.sort((a, b) =>
      a.player.name.localeCompare(b.player.name),
    );
  }

  if (sort === "team") {
    return sorted.sort((a, b) => a.player.team.localeCompare(b.player.team));
  }

  if (sort === "share") {
    return sorted.sort((a, b) => {
      const aShare = "current" in a ? a.current.share : a.movement.current.share;
      const bShare = "current" in b ? b.current.share : b.movement.current.share;
      return bShare - aShare;
    });
  }

  if (sort === "gainers") {
    return sorted.sort((a, b) => {
      const aChange = "movement" in a ? a.movement.percentagePointChange : 0;
      const bChange = "movement" in b ? b.movement.percentagePointChange : 0;
      return bChange - aChange;
    });
  }

  if (sort === "decliners") {
    return sorted.sort((a, b) => {
      const aChange = "movement" in a ? a.movement.percentagePointChange : 0;
      const bChange = "movement" in b ? b.movement.percentagePointChange : 0;
      return aChange - bChange;
    });
  }

  return sorted.sort((a, b) => {
    const aChange =
      "movement" in a ? Math.abs(a.movement.percentagePointChange) : 0;
    const bChange =
      "movement" in b ? Math.abs(b.movement.percentagePointChange) : 0;
    return bChange - aChange;
  });
}

function CurrentResultRow({
  row,
  onOpen,
}: {
  row: CurrentEvidenceRow;
  onOpen: (trigger: HTMLButtonElement) => void;
}) {
  return (
    <article className="report-result-row report-current-row" data-testid="report-row">
      <span className="report-rank">{row.authoritativeRank}</span>
      <span className="report-player-cell">
        <strong>{row.player.name}</strong>
        <small>
          {row.player.team} · {row.player.position} · {row.roleFamily}
        </small>
      </span>
      <span className="report-team-cell">
        <strong>{row.player.team}</strong>
        <small>{row.player.position}</small>
      </span>
      <span className="report-share-cell" data-share-evidence>
        <strong>{percent(row.current.share)}</strong>
        <small>
          {row.current.numerator} of {row.current.denominator}{" "}
          {row.current.opportunityLabel}
        </small>
        <span className="report-share-track" aria-hidden="true">
          <span style={{ width: `${row.current.share * 100}%` }} />
        </span>
      </span>
      <span className="report-classification">
        <strong>{row.classificationLabel}</strong>
        <small>
          {row.supportingContext ? "Typical-game context supplied" : qualityLabels[row.dataQuality]}
        </small>
      </span>
      <button
        type="button"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`Open evidence for ${row.player.name}`}
      >
        Evidence
        <ArrowRightIcon />
      </button>
    </article>
  );
}

function MovementResultRow({
  row,
  onOpen,
}: {
  row: MovementEvidenceRow;
  onOpen: (trigger: HTMLButtonElement) => void;
}) {
  const decline = row.direction === "decline";

  return (
    <article
      className={`report-result-row report-movement-row report-movement-${row.direction}`}
      data-testid="report-row"
    >
      <span className="report-rank">{row.authoritativeRank}</span>
      <span className="report-player-cell">
        <strong>{row.player.name}</strong>
        <small>
          {row.player.team} · {row.player.position} · {row.roleFamily}
        </small>
      </span>
      <span className="movement-period movement-period-prior" data-prior-evidence>
        <small>Previous</small>
        <strong>{percent(row.movement.previous.share)}</strong>
        <span>
          {row.movement.previous.numerator} of{" "}
          {row.movement.previous.denominator}{" "}
          {row.movement.previous.opportunityLabel}
        </span>
      </span>
      <span className="movement-direction" aria-label={`${row.direction} from previous to current`}>
        {decline ? <TrendDownIcon /> : <TrendUpIcon />}
        <span>Previous to current</span>
      </span>
      <span className="movement-period movement-period-current" data-current-evidence>
        <small>Current</small>
        <strong>{percent(row.movement.current.share)}</strong>
        <span>
          {row.movement.current.numerator} of {row.movement.current.denominator}{" "}
          {row.movement.current.opportunityLabel}
        </span>
      </span>
      <span className="movement-finding">
        <strong>{points(row.movement.percentagePointChange)}</strong>
        <small>{row.finding}</small>
      </span>
      <button
        type="button"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`Open evidence for ${row.player.name}`}
      >
        Evidence
        <ArrowRightIcon />
      </button>
    </article>
  );
}

function EvidenceDrawer({
  row,
  report,
  viewLabel,
  onClose,
}: {
  row: ResultRow;
  report: PublishedReport;
  viewLabel: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const current = "current" in row ? row.current : row.movement.current;

  return (
    <div className="evidence-overlay" onMouseDown={onClose}>
      <aside
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-drawer-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="evidence-drawer-heading">
          <span>
            <ReportsIcon />
            Evidence detail
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close evidence detail"
            autoFocus
          >
            Close
          </button>
        </div>

        <div className="evidence-drawer-body">
          <span className="evidence-drawer-context">
            {report.title} · {viewLabel}
          </span>
          <h2 id="evidence-drawer-title">{row.player.name}</h2>
          <p>
            {row.player.team} · {row.player.position} · {row.roleFamily}
          </p>

          {"movement" in row && (
            <div className="drawer-movement">
              <span>
                <small>Previous</small>
                <strong>{percent(row.movement.previous.share)}</strong>
                <em>
                  {row.movement.previous.numerator} of{" "}
                  {row.movement.previous.denominator}{" "}
                  {row.movement.previous.opportunityLabel}
                </em>
              </span>
              <ArrowRightIcon />
              <span>
                <small>Current</small>
                <strong>{percent(row.movement.current.share)}</strong>
                <em>
                  {row.movement.current.numerator} of{" "}
                  {row.movement.current.denominator}{" "}
                  {row.movement.current.opportunityLabel}
                </em>
              </span>
              <span className={`drawer-change drawer-change-${row.direction}`}>
                {points(row.movement.percentagePointChange)}
              </span>
            </div>
          )}

          {"current" in row && (
            <div className="drawer-current" data-share-evidence>
              <span>Authoritative all-play share</span>
              <strong>{percent(current.share)}</strong>
              <small>
                {current.numerator} of {current.denominator}{" "}
                {current.opportunityLabel}
              </small>
              <span className="report-share-track" aria-hidden="true">
                <span style={{ width: `${current.share * 100}%` }} />
              </span>
            </div>
          )}

          {row.supportingContext && (
            <div className="drawer-supporting">
              <span>Supporting context</span>
              <strong>{row.supportingContext.label}</strong>
              <small>
                {percent(row.supportingContext.evidence.share)} ·{" "}
                {row.supportingContext.evidence.numerator} of{" "}
                {row.supportingContext.evidence.denominator}{" "}
                {row.supportingContext.evidence.opportunityLabel}
              </small>
            </div>
          )}

          <dl className="evidence-metadata">
            <div>
              <dt>Data quality</dt>
              <dd>{qualityLabels[row.dataQuality]}</dd>
            </div>
            <div>
              <dt>Published through</dt>
              <dd>2025 · Week {report.throughWeek}</dd>
            </div>
            <div>
              <dt>Source version</dt>
              <dd>{report.sourceVersion}</dd>
            </div>
          </dl>

          <div className="drawer-links">
            <Link href={row.playerHref}>Future player page</Link>
            <Link href={row.teamHref}>Future team page</Link>
            <Link href="/methodology">Plain-language methodology</Link>
          </div>
        </div>
      </aside>
    </div>
  );
}

export function ReportExperience({
  data,
  initialQuery,
}: {
  data: PublishedReport;
  initialQuery: ParsedReportQuery;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const pendingParams = useRef(searchParams.toString());
  const [selectedRow, setSelectedRow] = useState<ResultRow | null>(null);
  const [copied, setCopied] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const evidenceTrigger = useRef<HTMLButtonElement | null>(null);
  const view = data.views.find((item) => item.viewId === initialQuery.view) ?? data.views[0];
  const viewOption =
    data.availableViews.find((item) => item.id === view.viewId) ??
    data.availableViews[0];
  const allRows = view.rows as readonly ResultRow[];
  const rows = useMemo(() => {
    const filtered = allRows.filter((row) => {
      const teamMatch =
        initialQuery.team === "ALL" || row.player.team === initialQuery.team;
      const positionMatch =
        data.reportFamily !== "target_hierarchy" ||
        initialQuery.position === "ALL" ||
        row.player.position === initialQuery.position;
      return teamMatch && positionMatch;
    });
    return sortRows(filtered, initialQuery.sort);
  }, [
    allRows,
    data.reportFamily,
    initialQuery.position,
    initialQuery.sort,
    initialQuery.team,
  ]);

  const activeFilterCount =
    Number(initialQuery.team !== "ALL") +
    Number(
      data.reportFamily === "target_hierarchy" &&
        initialQuery.position !== "ALL",
    );

  useEffect(() => {
    setFiltersOpen(window.matchMedia("(min-width: 721px)").matches);
  }, []);

  useEffect(() => {
    pendingParams.current = searchParams.toString();
  }, [searchParams]);

  const updateParam = (name: string, value: string, defaultValue?: string) => {
    const next = new URLSearchParams(pendingParams.current);
    if (!value || value === defaultValue) {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    next.delete("page");
    pendingParams.current = next.toString();
    router.push(`${pathname}${next.size ? `?${next.toString()}` : ""}`);
  };

  const resetFilters = () => {
    const next = new URLSearchParams();
    if (initialQuery.view !== data.defaultView) {
      next.set("view", initialQuery.view);
    }
    if (initialQuery.sort !== data.defaultSort) {
      next.set("sort", initialQuery.sort);
    }
    pendingParams.current = next.toString();
    router.push(`${pathname}${next.size ? `?${next.toString()}` : ""}`);
  };

  const copyView = async () => {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const openEvidence = (row: ResultRow, trigger: HTMLButtonElement) => {
    evidenceTrigger.current = trigger;
    setSelectedRow(row);
  };

  const closeEvidence = () => {
    setSelectedRow(null);
    window.requestAnimationFrame(() => evidenceTrigger.current?.focus());
  };

  return (
    <div className="report-page">
      <header className="report-header">
        <div className="report-title-block">
          <span>Report · 2025 Week {data.throughWeek}</span>
          <h1>{data.title}</h1>
          <p>{data.question}</p>
        </div>
        <div className="report-freshness">
          <StatusIcon />
          <span>
            <strong>
              {data.dataMode === "export"
                ? "Published export"
                : "Published fixture"}
            </strong>
            <small>Generated {new Date(data.generatedAt).toLocaleDateString("en-US")}</small>
          </span>
        </div>
      </header>

      <nav className="report-switcher" aria-label="Report family">
        {reportLinks.map((link) => (
          <Link
            href={link.href}
            key={link.family}
            aria-current={data.reportFamily === link.family ? "page" : undefined}
          >
            {link.label}
          </Link>
        ))}
      </nav>

      <section className="report-summary" aria-labelledby="report-answer">
        <div>
          <span>Answer first</span>
          <h2 id="report-answer">{view.summary.answer}</h2>
          <p>{data.description}</p>
        </div>
        <div className="report-summary-metrics">
          {view.summary.items.map((item) => (
            <span key={item.label}>
              <small>{item.label}</small>
              <strong>{item.value}</strong>
              <em>{item.detail}</em>
            </span>
          ))}
        </div>
      </section>

      <details
        className="report-controls"
        open={filtersOpen}
        onToggle={(event) => setFiltersOpen(event.currentTarget.open)}
      >
        <summary>
          <span>Filters</span>
          <strong>{activeFilterCount}</strong>
        </summary>
        <div className="report-control-fields">
          <label>
            <span>View</span>
            <select
              aria-label="View"
              value={initialQuery.view}
              onChange={(event) =>
                updateParam("view", event.target.value, data.defaultView)
              }
            >
              {data.availableViews.map((option) => (
                <option value={option.id} key={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Team</span>
            <select
              aria-label="Team"
              value={initialQuery.team}
              onChange={(event) =>
                updateParam("team", event.target.value, "ALL")
              }
            >
              {data.teamOptions.map((team) => (
                <option value={team} key={team}>
                  {team === "ALL" ? "All teams" : team}
                </option>
              ))}
            </select>
          </label>
          {data.reportFamily === "target_hierarchy" && (
            <label>
              <span>Position</span>
              <select
                aria-label="Position"
                value={initialQuery.position}
                onChange={(event) =>
                  updateParam("position", event.target.value, "ALL")
                }
              >
                <option value="ALL">All</option>
                <option value="WR">WR</option>
                <option value="TE">TE</option>
              </select>
            </label>
          )}
          <label>
            <span>Sort</span>
            <select
              aria-label="Sort"
              value={initialQuery.sort}
              onChange={(event) =>
                updateParam("sort", event.target.value, data.defaultSort)
              }
            >
              {data.availableSorts.map((option) => (
                <option value={option.id} key={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="report-reset" onClick={resetFilters}>
            Reset
          </button>
          <button type="button" className="report-copy" onClick={copyView}>
            {copied ? "Link copied" : "Copy link"}
          </button>
        </div>
      </details>

      <div className="report-results-heading">
        <span>
          <strong>{rows.length}</strong> supplied results
        </span>
        <small>
          {viewOption.currentPeriod.label}
          {viewOption.priorPeriod ? ` vs ${viewOption.priorPeriod.label}` : ""}
        </small>
      </div>

      {rows.length === 0 ? (
        <section className="report-no-match" aria-labelledby="no-match-title">
          <MinusIcon />
          <div>
            <span>No matching filters</span>
            <h2 id="no-match-title">No supplied rows match this view</h2>
            <p>
              The report is published, but the current team and position
              filters return no supplied rows.
            </p>
            <button type="button" onClick={resetFilters}>
              Reset filters
            </button>
          </div>
        </section>
      ) : (
        <section
          className={`report-results report-results-${data.reportFamily}`}
          aria-label={`${data.title} results`}
        >
          <div className="report-column-headings" aria-hidden="true">
            {data.reportFamily === "role_movement" ? (
              <>
                <span>Rank</span>
                <span>Player</span>
                <span>Previous</span>
                <span>Transition</span>
                <span>Current</span>
                <span>Movement</span>
                <span>Evidence</span>
              </>
            ) : (
              <>
                <span>Rank</span>
                <span>Player</span>
                <span>Team</span>
                <span>Current share</span>
                <span>Supplied role</span>
                <span>Evidence</span>
              </>
            )}
          </div>
          {rows.map((row) =>
            "movement" in row ? (
              <MovementResultRow
                key={row.id}
                row={row}
                onOpen={(trigger) => openEvidence(row, trigger)}
              />
            ) : (
              <CurrentResultRow
                key={row.id}
                row={row}
                onOpen={(trigger) => openEvidence(row, trigger)}
              />
            ),
          )}
        </section>
      )}

      <footer className="report-footer">
        <span>Authority rank and labels are bundle supplied.</span>
        <div>
          <Link href="/methodology">Methodology</Link>
          <Link href="/data-status">Data status</Link>
        </div>
      </footer>

      {selectedRow && (
        <EvidenceDrawer
          row={selectedRow}
          report={data}
          viewLabel={viewOption.label}
          onClose={closeEvidence}
        />
      )}
    </div>
  );
}
