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

const findingLabels: Record<FeedFinding["kind"], string> = {
  backfield_increase: "Backfield gain",
  target_share_increase: "Target-share gain",
  role_decline: "Role decline",
  concentrated_role: "Concentrated role",
  committee_formation: "Committee forming",
};

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

const signedPoints = (value: number, compact = false) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)}${compact ? " pp" : " percentage points"}`;

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

  const movement = finding.movement;

  return (
    <article className="dashboard-panel lead-panel" aria-labelledby="lead-finding-heading">
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <TrendUpIcon />
        </span>
        <span className="panel-label">Lead finding</span>
        <span className="panel-context">{reportLabels[finding.reportFamily]}</span>
      </div>

      <div className="lead-body">
        <div className="lead-story">
          <div className="lead-player">
            <span className="player-initials" aria-hidden="true">
              {finding.player.name
                .split(" ")
                .map((part) => part[0])
                .join("")}
            </span>
            <span>
              <strong>{finding.player.name}</strong>
              <small>
                {finding.player.team} · {finding.player.position} · {finding.roleFamily}
              </small>
            </span>
          </div>

          <h1 id="lead-finding-heading">{finding.headline}</h1>

          <Link className="primary-action" href={finding.evidenceHref}>
            Open supporting evidence
            <ArrowRightIcon />
          </Link>
        </div>

        <div className="lead-shift" aria-label="Previous and current role evidence">
          <div className="lead-change">
            <span>Weekly change</span>
            <strong>{signedPoints(movement.percentagePointChange)}</strong>
          </div>
          <div className="lead-evidence-pair">
            <ShareEvidence evidence={movement.previous} label="Previous" tone="prior" />
            <span className="evidence-arrow" aria-hidden="true">
              <ArrowRightIcon />
            </span>
            <ShareEvidence evidence={movement.current} label="Current" tone="gain" />
          </div>
        </div>
      </div>
    </article>
  );
}

function CompactFindingRow({ finding }: { finding: FeedFinding }) {
  const tone = findingTone(finding);

  return (
    <article className={`compact-finding compact-finding-${tone}`}>
      <span className={`trend-badge trend-badge-${tone}`} aria-hidden="true">
        <TrendIcon finding={finding} />
      </span>

      <div className="compact-identity">
        <strong>{finding.player.name}</strong>
        <small>
          {finding.player.team} · {finding.player.position} · {findingLabels[finding.kind]}
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
        <strong>
          {finding.movement
            ? signedPoints(finding.movement.percentagePointChange, true)
            : "Concentrated"}
        </strong>
        <Link href={finding.evidenceHref} aria-label={`Open evidence for ${finding.player.name}`}>
          Evidence
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
  const movementFindings = findings.slice(0, 3);
  const patternFindings = findings.slice(3);

  return (
    <>
      <section
        className="dashboard-panel movement-panel"
        aria-labelledby="role-change-feed-heading"
      >
        <div className="panel-heading">
          <span className="panel-icon panel-icon-gain" aria-hidden="true">
            <TrendUpIcon />
          </span>
          <h2 id="role-change-feed-heading">Role movement feed</h2>
          <Link href="/reports/movement" className="panel-link">
            View all
          </Link>
        </div>

        <div className="compact-list">
          {movementFindings.map((finding) => (
            <CompactFindingRow finding={finding} key={finding.id} />
          ))}
        </div>
      </section>

      <section className="dashboard-panel patterns-panel" aria-labelledby="role-patterns-heading">
        <div className="panel-heading">
          <span className="panel-icon panel-icon-amber" aria-hidden="true">
            <MinusIcon />
          </span>
          <h2 id="role-patterns-heading">Role shape changes</h2>
          <span className="panel-context">Concentration and committees</span>
        </div>

        <div className="pattern-list">
          {patternFindings.map((finding) => (
            <CompactFindingRow finding={finding} key={finding.id} />
          ))}
        </div>
      </section>
    </>
  );
}

export function ReportLinks({
  reports,
}: {
  reports: readonly ReportLink[];
}) {
  return (
    <aside className="dashboard-panel reports-panel" aria-labelledby="report-panel-heading">
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <ArrowRightIcon />
        </span>
        <h2 id="report-panel-heading">Evidence reports</h2>
        <span className="panel-context">Three report families</span>
      </div>

      <div className="report-list">
        {reports.map((report, index) => (
          <Link href={report.href} key={report.family}>
            <span className="report-index">{String(index + 1).padStart(2, "0")}</span>
            <span>
              <strong>{report.label}</strong>
              <small>{report.description}</small>
            </span>
            <ArrowRightIcon />
          </Link>
        ))}
      </div>

      <div className="report-footer">
        <span>Every share includes its matching raw count.</span>
        <Link href="/methodology">How we present evidence</Link>
      </div>
    </aside>
  );
}
