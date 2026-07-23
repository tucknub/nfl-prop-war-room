"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowRightIcon,
  MinusIcon,
  ReportsIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "@/components/icons";
import type { ReportLeaderboardFixture } from "@/lib/presentation-types";
import type { ReportFamily } from "@/lib/types";

const tabs: readonly { family: ReportFamily; label: string }[] = [
  { family: "backfield_control", label: "Backfield Control" },
  { family: "target_hierarchy", label: "Target Hierarchy" },
  { family: "role_movement", label: "Role Movement" },
];

const reportHrefs: Record<ReportFamily, string> = {
  backfield_control: "/reports/backfield",
  target_hierarchy: "/reports/targets",
  role_movement: "/reports/movement",
};

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const signedPoints = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

function MovementIndicator({ value }: { value: number }) {
  const className =
    value > 0
      ? "leaderboard-trend leaderboard-trend-up"
      : value < 0
        ? "leaderboard-trend leaderboard-trend-down"
        : "leaderboard-trend";

  return (
    <span
      className={className}
      aria-label={`${signedPoints(value)} movement`}
      role="cell"
    >
      {value > 0 ? (
        <TrendUpIcon />
      ) : value < 0 ? (
        <TrendDownIcon />
      ) : (
        <MinusIcon />
      )}
      {signedPoints(value)}
    </span>
  );
}

export function ReportLeaderboard({
  data,
}: {
  data: ReportLeaderboardFixture;
}) {
  const [activeFamily, setActiveFamily] =
    useState<ReportFamily>("backfield_control");
  const rows = data[activeFamily];

  return (
    <section
      className="dashboard-panel leaderboard-panel"
      aria-labelledby="report-leaderboard-heading"
      data-testid="report-leaderboard"
    >
      <div className="panel-heading">
        <span className="panel-icon panel-icon-gain" aria-hidden="true">
          <ReportsIcon />
        </span>
        <h2 id="report-leaderboard-heading">Report Leaderboard</h2>
        <Link href={reportHrefs[activeFamily]} className="panel-link">
          Full report
        </Link>
      </div>

      <div className="leaderboard-tabs" role="tablist" aria-label="Report family">
        {tabs.map((tab) => {
          const selected = activeFamily === tab.family;

          return (
            <button
              id={`leaderboard-tab-${tab.family}`}
              key={tab.family}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls="leaderboard-table"
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveFamily(tab.family)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        className="leaderboard-table"
        id="leaderboard-table"
        role="tabpanel"
        aria-live="polite"
      >
        <div className="leaderboard-columns" aria-hidden="true">
          <span>Rank</span>
          <span>Player</span>
          <span>Team</span>
          <span>{activeFamily === "role_movement" ? "Movement" : "Share"}</span>
          <span>Trend</span>
        </div>

        <div className="leaderboard-rows" role="table" aria-label={`${tabs.find((tab) => tab.family === activeFamily)?.label} rankings`}>
          {rows.map((row) => (
            <Link
              className="leaderboard-row"
              data-testid="leaderboard-row"
              href={row.evidenceHref}
              key={row.player.id}
              role="row"
            >
              <span className="leaderboard-rank" role="cell">
                {row.rank}
              </span>
              <span className="leaderboard-player" role="cell">
                <strong>{row.player.name}</strong>
                <small>
                  {row.player.position} · {row.evidence.numerator} of{" "}
                  {row.evidence.denominator} {row.evidence.opportunityLabel}
                </small>
              </span>
              <span className="leaderboard-team" role="cell">
                {row.player.team}
                <small>{row.player.position}</small>
              </span>
              <span className="leaderboard-metric" role="cell" data-share-evidence>
                <strong>
                  {activeFamily === "role_movement"
                    ? signedPoints(row.movementPoints)
                    : percent(row.evidence.share)}
                </strong>
                <small>
                  {row.evidence.numerator} of {row.evidence.denominator}{" "}
                  {row.evidence.opportunityLabel}
                </small>
              </span>
              <MovementIndicator value={row.movementPoints} />
            </Link>
          ))}
        </div>
      </div>

      <Link className="leaderboard-action" href={reportHrefs[activeFamily]}>
        View selected report
        <ArrowRightIcon />
      </Link>
    </section>
  );
}
