import Link from "next/link";
import {
  ArrowRightIcon,
  ReportsIcon,
  TrendUpIcon,
} from "@/components/icons";
import type { ReportsIndexBundle } from "@/lib/data-contract";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const points = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;
type ReportsIndexModule = ReportsIndexBundle["modules"][number];
type CurrentOverviewModule = Extract<ReportsIndexModule, { kind: "current" }>;
type MovementOverviewModule = Extract<ReportsIndexModule, { kind: "movement" }>;

export function ReportsOverview({ data }: { data: ReportsIndexBundle }) {
  const backfieldModule = data.modules.find(
    (module) =>
      module.kind === "current" &&
      module.family === "backfield_control",
  ) as CurrentOverviewModule | undefined;
  const targetModule = data.modules.find(
    (module) =>
      module.kind === "current" &&
      module.family === "target_hierarchy",
  ) as CurrentOverviewModule | undefined;
  const movementModule = data.modules.find(
    (module) => module.kind === "movement",
  ) as MovementOverviewModule | undefined;
  if (!backfieldModule || !targetModule || !movementModule) return null;
  const backfield = backfieldModule.row;
  const target = targetModule.row;
  const movement = movementModule.row;

  return (
    <>
      <div className="reports-overview-grid">
        <article className="report-family-card report-family-backfield">
          <div className="report-family-heading">
            <ReportsIcon />
            <span>Backfield Control</span>
            <strong>01</strong>
          </div>
          <h2>{backfieldModule.question}</h2>
          <div className="overview-player">
            <span className="overview-rank">1</span>
            <span>
              <strong>{backfield.player.name}</strong>
              <small>{backfield.evidenceTeam.id} · {backfield.player.position}</small>
            </span>
            <span className="overview-metric">
              <strong>{percent(backfield.current.share)}</strong>
              <small>
                {backfield.current.numerator} of {backfield.current.denominator}{" "}
                {backfield.current.opportunityLabel}
              </small>
            </span>
          </div>
          <p>{backfieldModule.description}</p>
          <Link href={backfieldModule.href}>
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
          <h2>{targetModule.question}</h2>
          <div className="overview-player">
            <span className="overview-rank">1</span>
            <span>
              <strong>{target.player.name}</strong>
              <small>{target.evidenceTeam.id} · {target.player.position}</small>
            </span>
            <span className="overview-metric">
              <strong>{percent(target.current.share)}</strong>
              <small>
                {target.current.numerator} of {target.current.denominator}{" "}
                {target.current.opportunityLabel}
              </small>
            </span>
          </div>
          <p>{targetModule.description}</p>
          <Link href={targetModule.href}>
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
          <h2>{movementModule.question}</h2>
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
          <Link href={movementModule.href}>
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
            The published bundle supplies both the player count and its matching
            team denominator. DepthSnap formats those values without rebuilding
            report membership or authority order.
          </p>
        </div>
        <div>
          <span>Supporting context</span>
          <h2>Typical-game evidence stays secondary.</h2>
          <p>
            When the bundle supplies a typical-game window, it is labeled as
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
