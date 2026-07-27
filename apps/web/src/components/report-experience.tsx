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
import {
  comparisonLabel,
  formatPercent,
  formatPoints,
  metricLabel,
  movementLabel,
  movementVerb,
  normalGameComparison,
  possessiveName,
} from "@/lib/consumer-presentation";
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

const reportQuestions = {
  backfield_control:
    "Who controls each team’s carries and total backfield opportunities?",
  target_hierarchy:
    "Who controls each team’s documented wide receiver and tight end targets?",
  role_movement:
    "Whose documented role changed most between the compared periods?",
} as const;

const participationLabels = {
  complete: "Complete participation record",
  suspected_statistical: "Possible partial participation",
  suspected_corroborated: "Corroborated partial participation",
  reviewed_partial_game: "Reviewed partial game",
} as const;

const movementRoleLabels = {
  rb_opportunity_share: "RB opportunity",
  rb_carry_share: "RB carry",
  wr_target_share: "WR target",
  te_target_share: "TE target",
} as const;

const movementRolePositions = {
  rb_opportunity_share: "RB",
  rb_carry_share: "RB",
  wr_target_share: "WR",
  te_target_share: "TE",
} as const;

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
    return sorted.sort((a, b) =>
      a.evidenceTeam.id.localeCompare(b.evidenceTeam.id),
    );
  }

  if (sort === "share" || sort === "share_asc") {
    return sorted.sort((a, b) => {
      const aShare = "current" in a ? a.current.share : a.movement.current.share;
      const bShare = "current" in b ? b.current.share : b.movement.current.share;
      return sort === "share" ? bShare - aShare : aShare - bShare;
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

function oneRowPerPlayer(rows: readonly ResultRow[]) {
  const seen = new Set<string>();
  return rows.filter((row) => {
    if (seen.has(row.player.id)) return false;
    seen.add(row.player.id);
    return true;
  });
}

function hasCaution(row: ResultRow) {
  return (
    row.participationQuality !== "complete" ||
    row.supportingContextStatus === "unavailable"
  );
}

function CurrentResultRow({
  row,
  onOpen,
}: {
  row: CurrentEvidenceRow;
  onOpen: (trigger: HTMLButtonElement) => void;
}) {
  const caution = hasCaution(row);
  return (
    <article
      className={`report-result-row report-current-row${caution ? " report-row-caution" : ""}`}
      data-testid="report-row"
      data-player-id={row.player.id}
    >
      <span className="report-player-cell">
        <strong>{row.player.name}</strong>
        <small>
          {row.evidenceTeam.name} · {row.player.position}
        </small>
      </span>
      <span className="report-share-cell" data-share-evidence>
        <strong>{formatPercent(row.current.share)}</strong>
        <small>
          {row.current.numerator} of {row.current.denominator}{" "}
          {row.current.opportunityLabel}
        </small>
        <span className="report-share-track" aria-hidden="true">
          <span style={{ width: `${row.current.share * 100}%` }} />
        </span>
      </span>
      {caution ? (
        <span className="report-context report-context-caution" role="note">
          <strong>Caution</strong>
          <small>
            {row.participationQuality !== "complete"
              ? participationLabels[row.participationQuality]
              : "Normal-game context unavailable"}
          </small>
        </span>
      ) : (
        <span className="report-context-placeholder" aria-hidden="true" />
      )}
      <button
        type="button"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`View evidence for ${row.player.name}`}
      >
        View evidence
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
  const change = row.movement.percentagePointChange;
  const direction = movementLabel(change);
  const caution = hasCaution(row);
  const DirectionIcon =
    change > 0 ? TrendUpIcon : change < 0 ? TrendDownIcon : MinusIcon;

  return (
    <article
      className={`report-result-row report-movement-row report-movement-${row.direction}${caution ? " report-row-caution" : ""}`}
      data-testid="report-row"
      data-movement-direction={row.direction}
      data-player-id={row.player.id}
    >
      <span className="report-player-cell">
        <strong>{row.player.name}</strong>
        <small>
          {row.evidenceTeam.name} · {row.player.position} · {row.roleLabel}
        </small>
      </span>
      <span className="movement-period movement-period-prior" data-prior-evidence>
        <small>Previous</small>
        <strong>{formatPercent(row.movement.previous.share)}</strong>
        <span>
          {row.movement.previous.numerator} of{" "}
          {row.movement.previous.denominator}{" "}
          {row.movement.previous.opportunityLabel}
        </span>
      </span>
      <span className="movement-period movement-period-current" data-current-evidence>
        <small>Current</small>
        <strong>{formatPercent(row.movement.current.share)}</strong>
        <span>
          {row.movement.current.numerator} of {row.movement.current.denominator}{" "}
          {row.movement.current.opportunityLabel}
        </span>
      </span>
      <span
        className={`movement-finding movement-finding-${row.direction}`}
        aria-label={`${direction}: ${formatPoints(change)}`}
      >
        <DirectionIcon />
        <span>
          <small>{direction}</small>
          <strong>{formatPoints(change)}</strong>
        </span>
      </span>
      <button
        type="button"
        onClick={(event) => onOpen(event.currentTarget)}
        aria-label={`View evidence for ${row.player.name}`}
      >
        View evidence
        <ArrowRightIcon />
      </button>
    </article>
  );
}

function EvidenceDrawer({
  row,
  report,
  period,
  onClose,
}: {
  row: ResultRow;
  report: PublishedReport;
  period: string;
  onClose: () => void;
}) {
  const drawerRef = useRef<HTMLElement>(null);
  const current = "current" in row ? row.current : row.movement.current;
  const caution = hasCaution(row);
  const evidenceVerb =
    current.opportunityLabel === "targets" ? "received" : "handled";
  const explanation =
    "movement" in row
      ? `${possessiveName(row.player.name)} ${row.roleLabel} ${movementVerb(
          row.movement.percentagePointChange,
        )} from ${formatPercent(row.movement.previous.share)} to ${formatPercent(
          row.movement.current.share,
        )} during ${period.toLowerCase()}.`
      : `${row.player.name} ${evidenceVerb} ${current.numerator} of ${possessiveName(row.evidenceTeam.name)} ${current.denominator} documented ${current.opportunityLabel} during ${period.toLowerCase()}.`;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  return (
    <div className="evidence-overlay" onMouseDown={onClose}>
      <aside
        ref={drawerRef}
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-drawer-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="evidence-drawer-heading">
          <span>
            <ReportsIcon />
            Evidence
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close evidence"
            autoFocus
          >
            Close
          </button>
        </div>

        <div className="evidence-drawer-body">
          <span className="evidence-drawer-context">
            {report.title} · {period}
          </span>
          <h2 id="evidence-drawer-title">{row.player.name}</h2>
          <p>{explanation}</p>

          {"movement" in row ? (
            <div className="drawer-movement">
              <span>
                <small>Previous</small>
                <strong>{formatPercent(row.movement.previous.share)}</strong>
                <em>
                  {row.movement.previous.numerator} of{" "}
                  {row.movement.previous.denominator}{" "}
                  {row.movement.previous.opportunityLabel}
                </em>
              </span>
              <ArrowRightIcon />
              <span>
                <small>Current</small>
                <strong>{formatPercent(row.movement.current.share)}</strong>
                <em>
                  {row.movement.current.numerator} of{" "}
                  {row.movement.current.denominator}{" "}
                  {row.movement.current.opportunityLabel}
                </em>
              </span>
              <span className={`drawer-change drawer-change-${row.direction}`}>
                {movementLabel(row.movement.percentagePointChange)} ·{" "}
                {formatPoints(row.movement.percentagePointChange)}
              </span>
            </div>
          ) : (
            <div className="drawer-current" data-share-evidence>
              <span>Current role</span>
              <strong>{formatPercent(current.share)}</strong>
              <small>
                {current.numerator} of {current.denominator}{" "}
                {current.opportunityLabel}
              </small>
              <span className="report-share-track" aria-hidden="true">
                <span style={{ width: `${current.share * 100}%` }} />
              </span>
            </div>
          )}

          <div className="drawer-supporting">
            <span>Normal-game comparison</span>
            {row.supportingContext ? (
              <>
                <strong>{row.supportingContext.label}</strong>
                <small>
                  {formatPercent(row.supportingContext.evidence.share)} ·{" "}
                  {row.supportingContext.evidence.numerator} of{" "}
                  {row.supportingContext.evidence.denominator}{" "}
                  {row.supportingContext.evidence.opportunityLabel}
                </small>
              </>
            ) : null}
            <p>
              {normalGameComparison(
                current,
                row.supportingContext?.evidence,
              )}
            </p>
          </div>

          {caution ? (
            <p className="drawer-caution" role="note">
              Caution: {participationLabels[row.participationQuality]}; normal-game
              context {row.supportingContextStatus}.
            </p>
          ) : null}

          <div className="drawer-links">
            <Link href={row.playerHref}>View player dossier</Link>
            <Link href={row.teamHref}>View team dossier</Link>
            <Link href="/methodology">How this is calculated</Link>
          </div>

          <details className="technical-details">
            <summary>Technical details</summary>
            <dl className="evidence-metadata">
              <div>
                <dt>Participation code</dt>
                <dd>{row.participationQuality}</dd>
              </div>
              <div>
                <dt>Context code</dt>
                <dd>{row.supportingContextStatus}</dd>
              </div>
              <div>
                <dt>Schema</dt>
                <dd>{report.schemaVersion}</dd>
              </div>
              <div>
                <dt>Source version</dt>
                <dd>{report.sourceVersion}</dd>
              </div>
            </dl>
          </details>
        </div>
      </aside>
    </div>
  );
}

function SegmentedControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="consumer-segmented">
      <legend>{label}</legend>
      <div>
        {options.map((option) => (
          <button
            type="button"
            key={option.value}
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
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
  const [visibleCount, setVisibleCount] = useState(25);
  const evidenceTrigger = useRef<HTMLButtonElement | null>(null);
  const view = data.views.find((item) => item.viewId === initialQuery.view) ?? data.views[0];
  const viewOption =
    data.availableViews.find((item) => item.id === view.viewId) ??
    data.availableViews[0];
  const period = comparisonLabel(
    viewOption.currentPeriod,
    viewOption.priorPeriod,
  );
  const allRows = view.rows as readonly ResultRow[];
  const movementPositions = useMemo(
    () =>
      ["RB", "WR", "TE"].filter((position) =>
        allRows.some((row) => row.player.position === position),
      ),
    [allRows],
  );
  const movementRoles = useMemo(
    () =>
      Object.keys(movementRoleLabels).filter((role) =>
        allRows.some((row) => row.roleFamily === role),
      ) as (keyof typeof movementRoleLabels)[],
    [allRows],
  );
  const effectiveSort: ReportSort =
    data.reportFamily === "role_movement" &&
    initialQuery.sort !== "authority"
      ? initialQuery.direction === "gains"
        ? "gainers"
        : initialQuery.direction === "declines"
          ? "decliners"
          : "absolute_change"
      : initialQuery.sort;

  const rows = useMemo(() => {
    const filtered = allRows.filter((row) => {
      const teamMatch =
        initialQuery.team === "ALL" ||
        row.evidenceTeam.id === initialQuery.team;
      const positionMatch =
        (data.reportFamily !== "target_hierarchy" &&
          data.reportFamily !== "role_movement") ||
        initialQuery.position === "ALL" ||
        row.player.position === initialQuery.position;
      const roleMatch =
        data.reportFamily !== "role_movement" ||
        initialQuery.role === "ALL" ||
        row.roleFamily === initialQuery.role;
      const metricMatch =
        data.reportFamily !== "backfield_control" ||
        ("current" in row &&
          row.current.opportunityLabel === initialQuery.metric);
      const directionMatch =
        data.reportFamily !== "role_movement" ||
        initialQuery.direction === "all" ||
        ("movement" in row &&
          row.direction ===
            (initialQuery.direction === "gains" ? "gain" : "decline"));
      return (
        teamMatch &&
        positionMatch &&
        roleMatch &&
        metricMatch &&
        directionMatch
      );
    });
    return sortRows(oneRowPerPlayer(filtered), effectiveSort);
  }, [
    allRows,
    data.reportFamily,
    effectiveSort,
    initialQuery.direction,
    initialQuery.metric,
    initialQuery.position,
    initialQuery.role,
    initialQuery.team,
  ]);
  const visibleRows = rows.slice(0, visibleCount);

  const footballOrder = useMemo(() => {
    const sort =
      data.reportFamily === "role_movement"
        ? initialQuery.direction === "declines"
          ? "decliners"
          : initialQuery.direction === "all"
            ? "absolute_change"
            : "gainers"
        : "share";
    return sortRows(rows, sort);
  }, [data.reportFamily, initialQuery.direction, rows]);

  const answer = useMemo(() => {
    if (!footballOrder.length) return "No players match the selected controls.";
    if (data.reportFamily === "role_movement") {
      const row = footballOrder[0] as MovementEvidenceRow;
      return `${row.player.name} has the largest ${movementLabel(
        row.movement.percentagePointChange,
      ).toLowerCase()} in this view: ${formatPercent(
        row.movement.previous.share,
      )} to ${formatPercent(row.movement.current.share)} (${formatPoints(
        row.movement.percentagePointChange,
      )}).`;
    }
    if (
      data.reportFamily === "target_hierarchy" &&
      initialQuery.team !== "ALL"
    ) {
      const teamRows = allRows.filter(
        (row): row is CurrentEvidenceRow =>
          "current" in row && row.evidenceTeam.id === initialQuery.team,
      );
      const wr = sortRows(
        oneRowPerPlayer(teamRows.filter((row) => row.player.position === "WR")),
        "share",
      )[0] as CurrentEvidenceRow | undefined;
      const te = sortRows(
        oneRowPerPlayer(teamRows.filter((row) => row.player.position === "TE")),
        "share",
      )[0] as CurrentEvidenceRow | undefined;
      return [
        wr
          ? `${wr.player.name} leads WRs with ${wr.current.numerator} of ${wr.current.denominator} targets.`
          : null,
        te
          ? `${te.player.name} leads TEs with ${te.current.numerator} of ${te.current.denominator} targets.`
          : null,
      ]
        .filter(Boolean)
        .join(" ");
    }
    const row = footballOrder[0] as CurrentEvidenceRow;
    return `${row.player.name} leads this view with ${row.current.numerator} of ${row.current.denominator} ${row.current.opportunityLabel} (${formatPercent(row.current.share)}).`;
  }, [
    allRows,
    data.reportFamily,
    footballOrder,
    initialQuery.team,
  ]);

  const teamCount = new Set(allRows.map((row) => row.evidenceTeam.id)).size;
  const activeFilterCount =
    Number(initialQuery.team !== "ALL") +
    Number(
      data.reportFamily === "target_hierarchy" &&
        initialQuery.position !== "WR",
    ) +
    Number(
      data.reportFamily === "backfield_control" &&
        initialQuery.metric !== "opportunities",
    ) +
    Number(
      data.reportFamily === "role_movement" &&
        initialQuery.direction !== "gains",
    ) +
    Number(
      data.reportFamily === "role_movement" &&
        initialQuery.position !== "ALL",
    ) +
    Number(
      data.reportFamily === "role_movement" && initialQuery.role !== "ALL",
    );

  useEffect(() => {
    setFiltersOpen(window.matchMedia("(min-width: 721px)").matches);
  }, []);

  useEffect(() => {
    pendingParams.current = searchParams.toString();
  }, [searchParams]);

  useEffect(() => {
    setVisibleCount(25);
  }, [
    initialQuery.view,
    initialQuery.sort,
    initialQuery.team,
    initialQuery.position,
    initialQuery.role,
    initialQuery.metric,
    initialQuery.direction,
  ]);

  const updateParams = (
    updates: Record<string, string | undefined>,
  ) => {
    const next = new URLSearchParams(pendingParams.current);
    for (const [name, value] of Object.entries(updates)) {
      if (!value) next.delete(name);
      else next.set(name, value);
    }
    next.delete("page");
    pendingParams.current = next.toString();
    router.push(`${pathname}${next.size ? `?${next.toString()}` : ""}`);
  };

  const resetFilters = () => {
    pendingParams.current = "";
    router.push(pathname);
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
          <span>{data.season} · Through Week {data.throughWeek}</span>
          <h1>{data.title}</h1>
          <p>{reportQuestions[data.reportFamily]}</p>
        </div>
        <div className="report-freshness">
          <StatusIcon />
          <span>
            <strong>
              {data.dataMode === "export" ? "Data verified" : "Interface preview"}
            </strong>
            <small>Updated through Week {data.throughWeek}</small>
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
          <h2 id="report-answer">{answer}</h2>
          <p>{period}</p>
        </div>
        <div className="report-compact-status" aria-label="Report freshness">
          <strong>Updated through Week {data.throughWeek}</strong>
          <span>{teamCount} teams</span>
          {data.reportFamily === "backfield_control" ? (
            <span>Minimum eight opportunities</span>
          ) : null}
          <span>Data verified</span>
        </div>
      </section>

      <details
        className="report-controls"
        open={filtersOpen}
        onToggle={(event) => setFiltersOpen(event.currentTarget.open)}
      >
        <summary>
          <span>Report controls</span>
          <strong>{activeFilterCount}</strong>
        </summary>
        <div className="report-control-fields">
          {data.reportFamily === "backfield_control" ? (
            <SegmentedControl
              label="Metric"
              value={initialQuery.metric}
              options={[
                { value: "opportunities", label: "Total opportunities" },
                { value: "carries", label: "Carries" },
              ]}
              onChange={(value) =>
                updateParams({
                  metric: value === "opportunities" ? undefined : value,
                })
              }
            />
          ) : null}
          {data.reportFamily === "target_hierarchy" ? (
            <SegmentedControl
              label="Position"
              value={initialQuery.position}
              options={[
                { value: "WR", label: "Wide receivers" },
                { value: "TE", label: "Tight ends" },
                { value: "ALL", label: "All" },
              ]}
              onChange={(value) =>
                updateParams({ position: value === "WR" ? undefined : value })
              }
            />
          ) : null}
          {data.reportFamily === "role_movement" ? (
            <>
              <SegmentedControl
                label="Direction"
                value={initialQuery.direction}
                options={[
                  { value: "gains", label: "Biggest gains" },
                  { value: "declines", label: "Biggest declines" },
                  { value: "all", label: "All movement" },
                ]}
                onChange={(value) =>
                  updateParams({
                    direction: value === "gains" ? undefined : value,
                  })
                }
              />
              <SegmentedControl
                label="Position"
                value={initialQuery.position}
                options={[
                  { value: "ALL", label: "All" },
                  ...movementPositions.map((position) => ({
                    value: position,
                    label: position,
                  })),
                ]}
                onChange={(value) => {
                  const selectedRole = initialQuery.role;
                  const compatible =
                    selectedRole === "ALL" ||
                    movementRolePositions[selectedRole] === value;
                  updateParams({
                    position: value === "ALL" ? undefined : value,
                    role: compatible
                      ? selectedRole === "ALL"
                        ? undefined
                        : selectedRole
                      : undefined,
                  });
                }}
              />
              <label>
                <span>Role</span>
                <select
                  aria-label="Role"
                  value={initialQuery.role}
                  onChange={(event) => {
                    const role = event.target
                      .value as ParsedReportQuery["role"];
                    updateParams({
                      role: role === "ALL" ? undefined : role,
                      position:
                        role === "ALL"
                          ? initialQuery.position === "ALL"
                            ? undefined
                            : initialQuery.position
                          : movementRolePositions[role],
                    });
                  }}
                >
                  <option value="ALL">All roles</option>
                  {movementRoles.map((role) => (
                    <option value={role} key={role}>
                      {movementRoleLabels[role]}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          <label>
            <span>Window</span>
            <select
              aria-label="Window"
              value={initialQuery.view}
              onChange={(event) =>
                updateParams({
                  view:
                    event.target.value === data.defaultView
                      ? undefined
                      : event.target.value,
                })
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
                updateParams({
                  team: event.target.value === "ALL" ? undefined : event.target.value,
                })
              }
            >
              {data.teamOptions.map((team) => (
                <option value={team} key={team}>
                  {team === "ALL" ? "All teams" : team}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Sort</span>
            {data.reportFamily === "role_movement" ? (
              <select
                aria-label="Sort"
                value={initialQuery.sort === "authority" ? "authority" : "movement"}
                onChange={(event) =>
                  updateParams({
                    sort:
                      event.target.value === "authority"
                        ? "authority"
                        : undefined,
                  })
                }
              >
                <option value="movement">Movement size</option>
                <option value="authority">Report order</option>
              </select>
            ) : (
              <select
                aria-label="Sort"
                value={initialQuery.sort}
                onChange={(event) =>
                  updateParams({
                    sort:
                      event.target.value === "share"
                        ? undefined
                        : event.target.value,
                  })
                }
              >
                <option value="share">Highest share</option>
                <option value="share_asc">Lowest share</option>
                <option value="authority">Report order</option>
              </select>
            )}
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
          Showing <strong>{Math.min(visibleCount, rows.length)}</strong> of{" "}
          <strong>{rows.length}</strong> players
        </span>
        <small>{period}</small>
      </div>

      {rows.length === 0 ? (
        <section className="report-no-match" aria-labelledby="no-match-title">
          <MinusIcon />
          <div>
            <span>No matching players</span>
            <h2 id="no-match-title">No players match these controls</h2>
            <p>
              The report is available, but this combination of team, metric,
              position, role, and direction has no qualifying result.
            </p>
            <button type="button" onClick={resetFilters}>
              Reset controls
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
                <span>Player</span>
                <span>Previous</span>
                <span>Current</span>
                <span>Change</span>
                <span>Evidence</span>
              </>
            ) : (
              <>
                <span>Player</span>
                <span>Current share</span>
                <span>Caution</span>
                <span>Evidence</span>
              </>
            )}
          </div>
          {visibleRows.map((row) =>
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
          {visibleCount < rows.length ? (
            <div className="report-reveal">
              <button
                type="button"
                onClick={() =>
                  setVisibleCount((count) =>
                    Math.min(count + 25, rows.length),
                  )
                }
              >
                Show 25 more
              </button>
            </div>
          ) : null}
        </section>
      )}

      <footer className="report-footer">
        <span>Every percentage includes its raw count.</span>
        <div>
          <Link href="/methodology">How this is calculated</Link>
          <Link href="/data-status">Data status</Link>
        </div>
      </footer>

      {selectedRow ? (
        <EvidenceDrawer
          row={selectedRow}
          report={data}
          period={period}
          onClose={closeEvidence}
        />
      ) : null}
    </div>
  );
}
