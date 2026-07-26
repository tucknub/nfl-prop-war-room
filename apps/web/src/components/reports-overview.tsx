import Link from "next/link";
import {
  ArrowRightIcon,
  ReportsIcon,
  TrendUpIcon,
} from "@/components/icons";
import { possessiveName } from "@/lib/consumer-presentation";
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
          <h2>Who controls each team’s backfield opportunities?</h2>
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
          <p>
            {backfield.player.name} controlled {backfield.current.numerator} of{" "}
            {possessiveName(backfield.evidenceTeam.name)}{" "}
            {backfield.current.denominator}{" "}
            documented {backfield.current.opportunityLabel} in this view.
          </p>
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
          <h2>Who controls each team’s documented targets?</h2>
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
          <p>
            {target.player.name} received {target.current.numerator} of{" "}
            {possessiveName(target.evidenceTeam.name)}{" "}
            {target.current.denominator} documented
            targets in this view.
          </p>
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
          <h2>Whose documented role changed the most?</h2>
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
          <p>
            {movement.player.name} recorded the largest first displayed role
            change in this view, with every percentage tied to its raw counts.
          </p>
          <Link href={movementModule.href}>
            Open Role Movement
            <ArrowRightIcon />
          </Link>
        </article>
      </div>

      <section className="reports-authority" aria-labelledby="reports-guide-title">
        <div>
          <span>Start with the answer</span>
          <h2 id="reports-guide-title">Each tool answers a different football question.</h2>
          <p>
            Backfield Control shows rushing workload, Target Hierarchy shows
            target ownership, and Role Movement shows recent changes.
          </p>
        </div>
        <div>
          <span>Then inspect the evidence</span>
          <h2>Exact counts stay attached to every share.</h2>
          <p>
            Open any result for normal-game context, participation cautions,
            compared periods, and optional technical details.
          </p>
        </div>
        <nav aria-label="Report documentation">
          <Link href="/methodology">How this is calculated</Link>
          <Link href="/data-status">Data Status</Link>
        </nav>
      </section>
    </>
  );
}
