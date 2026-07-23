import Link from "next/link";
import {
  ArrowRightIcon,
  ReportsIcon,
  TrendUpIcon,
} from "@/components/icons";
import {
  backfieldReportFixture,
  movementReportFixture,
  targetReportFixture,
} from "@/data/reports.fixture";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const points = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

export function ReportsOverview() {
  const backfield = backfieldReportFixture.views[0].rows[0];
  const target = targetReportFixture.views[0].rows[0];
  const movement = movementReportFixture.views[0].rows[0];

  return (
    <>
      <div className="reports-overview-grid">
        <article className="report-family-card report-family-backfield">
          <div className="report-family-heading">
            <ReportsIcon />
            <span>Backfield Control</span>
            <strong>01</strong>
          </div>
          <h2>Who owns each team’s documented RB opportunities?</h2>
          <div className="overview-player">
            <span className="overview-rank">1</span>
            <span>
              <strong>{backfield.player.name}</strong>
              <small>{backfield.player.team} · {backfield.player.position}</small>
            </span>
            <span className="overview-metric">
              <strong>{percent(backfield.current.share)}</strong>
              <small>
                {backfield.current.numerator} of {backfield.current.denominator}{" "}
                {backfield.current.opportunityLabel}
              </small>
            </span>
          </div>
          <p>
            Player opportunities stay paired with the matching team RB total.
          </p>
          <Link href="/reports/backfield">
            Open Backfield Control
            <ArrowRightIcon />
          </Link>
        </article>

        <article className="report-family-card report-family-targets">
          <div className="report-family-heading">
            <ReportsIcon />
            <span>Target Hierarchy</span>
            <strong>02</strong>
          </div>
          <h2>Who owns each team’s documented WR and TE targets?</h2>
          <div className="overview-player">
            <span className="overview-rank">1</span>
            <span>
              <strong>{target.player.name}</strong>
              <small>{target.player.team} · {target.player.position}</small>
            </span>
            <span className="overview-metric">
              <strong>{percent(target.current.share)}</strong>
              <small>
                {target.current.numerator} of {target.current.denominator}{" "}
                {target.current.opportunityLabel}
              </small>
            </span>
          </div>
          <p>WR and TE target evidence uses the supplied team target total.</p>
          <Link href="/reports/targets">
            Open Target Hierarchy
            <ArrowRightIcon />
          </Link>
        </article>

        <article className="report-family-card report-family-movement">
          <div className="report-family-heading">
            <TrendUpIcon />
            <span>Role Movement</span>
            <strong>03</strong>
          </div>
          <h2>Whose documented role changed most between supplied periods?</h2>
          <div className="overview-movement">
            <span>
              <small>Previous</small>
              <strong>{percent(movement.movement.previous.share)}</strong>
              <em>
                {movement.movement.previous.numerator} of{" "}
                {movement.movement.previous.denominator}
              </em>
            </span>
            <ArrowRightIcon />
            <span>
              <small>Current</small>
              <strong>{percent(movement.movement.current.share)}</strong>
              <em>
                {movement.movement.current.numerator} of{" "}
                {movement.movement.current.denominator}
              </em>
            </span>
            <span className="overview-change">
              <small>{movement.player.name}</small>
              <strong>{points(movement.movement.percentagePointChange)}</strong>
            </span>
          </div>
          <Link href="/reports/movement">
            Open Role Movement
            <ArrowRightIcon />
          </Link>
        </article>
      </div>

      <section className="reports-authority" aria-labelledby="reports-authority-title">
        <div>
          <span>All-play authority</span>
          <h2 id="reports-authority-title">Exact counts stay attached to every share.</h2>
          <p>
            The published fixture supplies both the player count and its matching
            team denominator. DepthSnap formats those values without rebuilding
            report membership or authority order.
          </p>
        </div>
        <div>
          <span>Supporting context</span>
          <h2>Typical-game evidence stays secondary.</h2>
          <p>
            When the fixture supplies a typical-game window, it is labeled as
            supporting context rather than replacing the authoritative all-play
            result.
          </p>
        </div>
        <nav aria-label="Report documentation">
          <Link href="/methodology">Future Methodology</Link>
          <Link href="/data-status">Data Status</Link>
        </nav>
      </section>
    </>
  );
}
