import Link from "next/link";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  MinusIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "@/components/icons";
import type {
  FeedFinding,
  RawShareEvidence,
  ReportFamily,
  ReportLink,
} from "@/lib/types";

const reportLabels: Record<ReportFamily, string> = {
  backfield_control: "Backfield Control",
  target_hierarchy: "Target Hierarchy",
  role_movement: "Role Movement",
};

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

const signedPoints = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} percentage points`;

function findingTone(finding: FeedFinding) {
  if (finding.kind === "role_decline" || finding.kind === "committee_formation") {
    return "decline";
  }

  if (finding.kind === "concentrated_role") {
    return "concentration";
  }

  return "gain";
}

function TrendIcon({ finding }: { finding: FeedFinding }) {
  const tone = findingTone(finding);

  if (tone === "decline") {
    return <TrendDownIcon />;
  }

  if (tone === "concentration") {
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
  tone?: "gain" | "decline" | "concentration" | "prior";
  compact?: boolean;
}) {
  return (
    <div
      className={`share-evidence share-evidence-${tone}${compact ? " share-evidence-compact" : ""}`}
      data-share-evidence
    >
      <span className="evidence-label">{label}</span>
      <strong className="evidence-percentage">{percent(evidence.share)}</strong>
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

export function LeadFinding({ finding }: { finding: FeedFinding }) {
  if (!finding.movement) {
    return null;
  }

  return (
    <article className="lead-finding" aria-labelledby="lead-finding-heading">
      <div className="lead-copy">
        <div className="finding-family">
          <span className="family-index">01</span>
          <span>{reportLabels[finding.reportFamily]}</span>
        </div>
        <div className="player-identity">
          <span className="player-initials" aria-hidden="true">
            {finding.player.name
              .split(" ")
              .map((part) => part[0])
              .join("")}
          </span>
          <span>
            <strong>{finding.player.name}</strong>
            <small>
              {finding.player.team} · {finding.player.position} ·{" "}
              {finding.roleFamily}
            </small>
          </span>
        </div>
        <h1 id="lead-finding-heading">{finding.headline}</h1>
        <Link className="evidence-link" href={finding.evidenceHref}>
          Open supporting evidence
          <ArrowUpRightIcon />
        </Link>
      </div>

      <div
        className="lead-comparison"
        aria-label="Previous and current role evidence"
      >
        <ShareEvidence
          evidence={finding.movement.previous}
          label="Previous"
          tone="prior"
        />
        <span className="comparison-divider" aria-hidden="true" />
        <ShareEvidence
          evidence={finding.movement.current}
          label="Current"
          tone="gain"
        />
        <div className="lead-change">
          <span>Change</span>
          <strong>
            {signedPoints(finding.movement.percentagePointChange)}
          </strong>
        </div>
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
    <section className="feed-section" aria-labelledby="role-change-feed-heading">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Weekly evidence</span>
          <h2 id="role-change-feed-heading">Role-change feed</h2>
        </div>
        <Link href="/reports/movement" className="section-link">
          View all movement
          <ArrowRightIcon />
        </Link>
      </div>

      <div className="feed-list">
        {findings.map((finding, index) => {
          const tone = findingTone(finding);
          return (
            <article className={`feed-row feed-row-${tone}`} key={finding.id}>
              <div className="feed-order" aria-hidden="true">
                {String(index + 2).padStart(2, "0")}
              </div>

              <div className={`trend-marker trend-marker-${tone}`}>
                <TrendIcon finding={finding} />
                <span>{reportLabels[finding.reportFamily]}</span>
              </div>

              <div className="feed-summary">
                <div className="feed-player">
                  <strong>{finding.player.name}</strong>
                  <span>
                    {finding.player.team} · {finding.player.position}
                  </span>
                </div>
                <h3>{finding.headline}</h3>
                <span className="role-family">{finding.roleFamily}</span>
              </div>

              <div className="feed-evidence">
                {finding.movement ? (
                  <ShareEvidence
                    evidence={finding.movement.previous}
                    label="Previous"
                    tone="prior"
                    compact
                  />
                ) : (
                  <span className="no-prior">Current role concentration</span>
                )}
                <ShareEvidence
                  evidence={finding.current}
                  label="Current"
                  tone={tone}
                  compact
                />
              </div>

              <div className="feed-action">
                {finding.movement ? (
                  <span className={`movement-value movement-value-${tone}`}>
                    {signedPoints(finding.movement.percentagePointChange)}
                  </span>
                ) : (
                  <span className="movement-value movement-value-concentration">
                    Concentrated role
                  </span>
                )}
                <Link href={finding.evidenceHref} aria-label={`Open evidence for ${finding.player.name}`}>
                  Evidence
                  <ArrowUpRightIcon />
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function ReportLinks({
  reports,
}: {
  reports: readonly ReportLink[];
}) {
  return (
    <aside className="report-rail" aria-labelledby="report-rail-heading">
      <div className="report-rail-intro">
        <span className="section-kicker">Three reports</span>
        <h2 id="report-rail-heading">Follow the evidence</h2>
      </div>
      <div className="report-links">
        {reports.map((report, index) => (
          <Link href={report.href} key={report.family}>
            <span className="report-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span>
              <strong>{report.label}</strong>
              <small>{report.description}</small>
            </span>
            <ArrowRightIcon />
          </Link>
        ))}
      </div>
    </aside>
  );
}
