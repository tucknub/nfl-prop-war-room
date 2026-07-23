import Image from "next/image";
import Link from "next/link";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  MinusIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "@/components/icons";
import type { FeedFinding, RawShareEvidence, ReportFamily } from "@/lib/types";

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

  return (
    <article className="dashboard-panel lead-panel" aria-labelledby="lead-finding-heading">
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <TrendUpIcon />
        </span>
        <span className="panel-label">Lead finding</span>
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
                {finding.player.team} · {finding.player.position} · {finding.roleFamily}
              </small>
            </span>
          </div>

          <h1 id="lead-finding-heading">{finding.headline}</h1>
          <p className="lead-summary">
            His documented opportunity share moved from{" "}
            {percent(movement.previous.share)} to {percent(movement.current.share)}.
          </p>

          <div className="lead-actions">
            <Link className="primary-action" href={finding.evidenceHref}>
              Open supporting evidence
              <ArrowRightIcon />
            </Link>
            <span className="lead-change">
              <small>Weekly change</small>
              <strong>{signedPoints(movement.percentagePointChange, true)}</strong>
            </span>
          </div>

          <div className="lead-shift" aria-label="Previous and current role evidence">
            <ShareEvidence evidence={movement.previous} label="Previous" tone="prior" />
            <span className="evidence-arrow" aria-hidden="true">
              <ArrowRightIcon />
            </span>
            <ShareEvidence evidence={movement.current} label="Current" tone="gain" />
          </div>
        </div>

        <div
          className="lead-media"
          data-testid="lead-media"
          aria-label="Fictional football athlete in action"
        >
          <Image
            src="/images/depthsnap-athlete.png"
            alt="Fictional football running back carrying the ball"
            fill
            priority
            sizes="(max-width: 720px) 100vw, 46vw"
          />
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
        <small>Movement</small>
        <strong>
          {finding.movement
            ? signedPoints(finding.movement.percentagePointChange, true)
            : "Supported"}
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
  return (
    <section
      className="dashboard-panel movement-panel"
      aria-labelledby="role-change-feed-heading"
    >
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <TrendUpIcon />
        </span>
        <h2 id="role-change-feed-heading">Role Movement Feed</h2>
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
