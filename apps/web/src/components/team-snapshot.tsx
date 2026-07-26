import Link from "next/link";
import { ArrowRightIcon, TeamsIcon, TrendUpIcon } from "@/components/icons";
import type { TeamSnapshotFixture } from "@/lib/presentation-types";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export function TeamSnapshot({ data }: { data: TeamSnapshotFixture }) {
  return (
    <section
      className="dashboard-panel team-panel"
      aria-labelledby="team-snapshot-heading"
      data-testid="team-snapshot"
    >
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <TeamsIcon />
        </span>
        <h2 id="team-snapshot-heading">Team Snapshot</h2>
        <span className="week-control">Week {data.week}</span>
      </div>

      <div className="team-identity">
        <span className="team-monogram" aria-hidden="true">
          {data.monogram}
        </span>
        <span>
          <strong>{data.teamName}</strong>
          <small>{data.teamCode} · documented evidence team</small>
        </span>
      </div>

      <div className="team-share-list" aria-label="Team role shares">
        {data.rows.map((row) => (
          <div
            className={`team-share-row team-share-row-${row.tone}`}
            data-share-evidence
            key={row.role}
          >
            <span className="team-role">{row.role}</span>
            <span className="team-player">{row.player}</span>
            <span className="team-bar" aria-hidden="true">
              <span style={{ width: `${row.evidence.share * 100}%` }} />
            </span>
            <strong>{percent(row.evidence.share)}</strong>
            <small>
              {row.evidence.numerator} of {row.evidence.denominator}{" "}
              {row.evidence.opportunityLabel}
            </small>
          </div>
        ))}
      </div>

      {data.biggestMovement ? (
        <div className="team-movement">
          <span className="team-movement-icon" aria-hidden="true">
            <TrendUpIcon />
          </span>
          <span>
            <small>Biggest documented movement</small>
            <strong>{data.biggestMovement.player}</strong>
            <span>{data.biggestMovement.summary}</span>
          </span>
          <strong>
            {data.biggestMovement.percentagePointChange > 0 ? "+" : ""}
            {data.biggestMovement.percentagePointChange.toFixed(1)} pp
          </strong>
        </div>
      ) : null}

      <Link className="team-report-action" href={data.reportHref}>
        View team dossier
        <ArrowRightIcon />
      </Link>
    </section>
  );
}
