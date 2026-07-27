import Link from "next/link";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  MinusIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "@/components/icons";
import {
  formatPercent,
  formatPoints,
  movementHeadline,
  movementLabel,
  rollingFourWeekComparison,
} from "@/lib/consumer-presentation";
import type { FeedFinding, RawShareEvidence, ReportFamily } from "@/lib/types";

const reportLabels: Record<ReportFamily, string> = {
  backfield_control: "Backfield Control",
  target_hierarchy: "Target Hierarchy",
  role_movement: "Role Movement",
};

function findingTone(finding: FeedFinding) {
  if (finding.kind === "opportunity_lost") {
    return "decline";
  }

  if (
    finding.kind === "box_score_overstated_role" ||
    finding.kind === "strong_opportunity_weak_production"
  ) {
    return "caution";
  }

  return "gain";
}

function TrendIcon({ finding }: { finding: FeedFinding }) {
  const tone = findingTone(finding);

  if (tone === "decline") {
    return <TrendDownIcon />;
  }

  if (tone === "caution") {
    return <MinusIcon />;
  }

  return <TrendUpIcon />;
}

export function ShareEvidence({
  evidence,
  label,
  tone = "gain",
  compact = false,
}: {
  evidence: RawShareEvidence;
  label: string;
  tone?: "gain" | "decline" | "caution" | "prior";
  compact?: boolean;
}) {
  return (
    <div
      className={`share-evidence share-evidence-${tone}${compact ? " share-evidence-compact" : ""}`}
      data-share-evidence
    >
      <span className="evidence-label">{label}</span>
      <strong className="evidence-percentage">{formatPercent(evidence.share)}</strong>
      <span className="evidence-raw">
        {evidence.numerator} of {evidence.denominator} {evidence.opportunityLabel}
      </span>
      <span className="share-track" aria-hidden="true">
        <span
          className="share-fill"
          style={{ width: `${Math.min(evidence.share * 100, 100)}%` }}
        />
      </span>
    </div>
  );
}

export function LeadFinding({
  finding,
  week,
}: {
  finding: FeedFinding;
  week: number;
}) {
  if (!finding.movement) {
    return null;
  }

  const movement = finding.movement;
  const tone =
    movement.percentagePointChange > 0
      ? "gain"
      : movement.percentagePointChange < 0
        ? "decline"
        : "neutral";
  const DirectionIcon =
    tone === "gain"
      ? TrendUpIcon
      : tone === "decline"
        ? TrendDownIcon
        : MinusIcon;
  const caution =
    finding.kind === "box_score_overstated_role" ||
    finding.kind === "strong_opportunity_weak_production" ||
    finding.participationQuality !== "complete" ||
    finding.supportingContextStatus === "unavailable";
  const illustrationLabel =
    finding.player.position === "RB"
      ? `${finding.evidenceTeam.name} backfield role illustration`
      : `${finding.evidenceTeam.name} target role illustration`;

  return (
    <article className="dashboard-panel lead-panel" aria-labelledby="lead-finding-heading">
      <div className="panel-heading">
        <span className={`panel-icon panel-icon-${tone}`} aria-hidden="true">
          <DirectionIcon />
        </span>
        <span className="panel-label">Weekly briefing</span>
        <span className="panel-context">
          Week {week} · {reportLabels[finding.reportFamily]}
        </span>
      </div>

      <div className="lead-body">
        <div className="lead-story">
          <div className="lead-player">
            <span className="lead-player-number" aria-hidden="true">
              1
            </span>
            <span>
              <strong>{finding.player.name}</strong>
              <small>
                {finding.evidenceTeam.id} · {finding.player.position} · {finding.roleLabel}
              </small>
            </span>
          </div>

          <h1 id="lead-finding-heading">
            {movementHeadline(
              finding.player.name,
              finding.roleLabel,
              movement,
            )}
          </h1>
          <p className="lead-summary">
            {rollingFourWeekComparison(week)}
          </p>
          {caution ? (
            <p className="lead-caution" role="note">
              Caution: unusual game context or participation may affect how this
              change should be read.
            </p>
          ) : null}

          <div className="lead-actions">
            <Link className="primary-action" href={finding.evidenceHref}>
              View evidence
              <ArrowRightIcon />
            </Link>
            <span className="lead-change">
              <small>{movementLabel(movement.percentagePointChange)}</small>
              <strong>{formatPoints(movement.percentagePointChange)}</strong>
            </span>
          </div>

          <div className="lead-shift" aria-label="Previous and current role evidence">
            <ShareEvidence evidence={movement.previous} label="Previous" tone="prior" />
            <span className="evidence-arrow" aria-hidden="true">
              <ArrowRightIcon />
            </span>
            <ShareEvidence
              evidence={movement.current}
              label="Current"
              tone={tone === "neutral" ? "prior" : tone}
            />
          </div>
        </div>

        <div
          className="lead-media"
          data-testid="lead-media"
          role="img"
          aria-label={illustrationLabel}
        >
          <span className="role-illustration-field" aria-hidden="true">
            <span className="role-illustration-yard role-illustration-yard-one" />
            <span className="role-illustration-yard role-illustration-yard-two" />
            <span className="role-illustration-yard role-illustration-yard-three" />
            <span className="role-illustration-route" />
            <span className="role-illustration-node role-illustration-node-primary">
              {finding.player.position}
            </span>
            <span className="role-illustration-node role-illustration-node-secondary" />
            <span className="role-illustration-team">
              {finding.evidenceTeam.id}
            </span>
          </span>
          <span className="lead-media-caption">
            <strong>{finding.player.position}</strong>
            <span>Role control</span>
          </span>
        </div>
      </div>
    </article>
  );
}

function CompactFindingRow({ finding }: { finding: FeedFinding }) {
  const tone = findingTone(finding);
  const movementValue = finding.movement?.percentagePointChange;
  const direction =
    movementValue === undefined
      ? "Caution"
      : tone === "caution"
        ? "Caution"
        : movementLabel(movementValue);

  return (
    <article
      className={`compact-finding compact-finding-${tone}`}
      data-testid="movement-row"
    >
      <span className={`trend-badge trend-badge-${tone}`} aria-hidden="true">
        <TrendIcon finding={finding} />
      </span>

      <div className="compact-identity">
        <strong>{finding.player.name}</strong>
        <small>
          {finding.evidenceTeam.name} · {finding.player.position} · {direction}
        </small>
      </div>

      <div className="compact-transition">
        {finding.movement ? (
          <>
            <ShareEvidence
              evidence={finding.movement.previous}
              label="Previous"
              tone="prior"
              compact
            />
            <span className="row-arrow" aria-hidden="true">
              <ArrowRightIcon />
            </span>
          </>
        ) : (
          <span className="current-only">One-week evidence</span>
        )}
        <ShareEvidence
          evidence={finding.current}
          label="Current"
          tone={tone}
          compact
        />
      </div>

      <div className={`compact-change compact-change-${tone}`}>
        <small>Movement</small>
        <strong>
          {finding.movement
            ? formatPoints(finding.movement.percentagePointChange)
            : "Context note"}
        </strong>
        <span className="compact-direction-label">{direction}</span>
        <Link href={finding.evidenceHref} aria-label={`View evidence for ${finding.player.name}`}>
          View
          <ArrowUpRightIcon />
        </Link>
      </div>
    </article>
  );
}

export function RoleChangeFeed({
  findings,
}: {
  findings: readonly FeedFinding[];
}) {
  return (
    <section
      className="dashboard-panel movement-panel"
      aria-labelledby="role-change-feed-heading"
    >
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <TrendUpIcon />
        </span>
        <h2 id="role-change-feed-heading">Recent role changes</h2>
        <Link href="/reports/movement" className="panel-link">
          View all
        </Link>
      </div>

      <div className="compact-list">
        {findings.slice(0, 3).map((finding) => (
          <CompactFindingRow finding={finding} key={finding.id} />
        ))}
      </div>
    </section>
  );
}
