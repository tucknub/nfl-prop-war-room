"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PlayerMonogram, ShareEvidence } from "@/components/identity-primitives";
import type { PlayerDirectoryRecord } from "@/lib/identity-types";
import type { PlayerPosition, ReportFamily } from "@/lib/types";

export function PlayerDirectory({
  records,
  teams,
  initialQuery = "",
  initialTeam = "ALL",
  initialPosition = "ALL",
  initialReport = "ALL",
}: {
  records: readonly PlayerDirectoryRecord[];
  teams: readonly string[];
  initialQuery?: string;
  initialTeam?: string;
  initialPosition?: PlayerPosition | "ALL";
  initialReport?: ReportFamily | "ALL";
}) {
  const [query, setQuery] = useState(initialQuery);
  const [team, setTeam] = useState(teams.includes(initialTeam) ? initialTeam : "ALL");
  const [position, setPosition] = useState<PlayerPosition | "ALL">(
    ["ALL", "RB", "WR", "TE"].includes(initialPosition) ? initialPosition : "ALL",
  );
  const [report, setReport] = useState<ReportFamily | "ALL">(
    ["ALL", "backfield_control", "target_hierarchy", "role_movement"].includes(initialReport)
      ? initialReport
      : "ALL",
  );
  const [sort, setSort] = useState<"alphabetical" | "authority">("alphabetical");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return records
      .filter((record) => record.player.name.toLowerCase().includes(normalized))
      .filter((record) => team === "ALL" || record.player.team === team)
      .filter((record) => position === "ALL" || record.player.position === position)
      .filter((record) => report === "ALL" || record.memberships.some((item) => item.family === report))
      .toSorted((left, right) => {
        if (sort === "alphabetical") {
          return left.player.name.localeCompare(right.player.name);
        }
        const leftRank = Math.min(...left.memberships.map((item) => item.authoritativeRank), 999);
        const rightRank = Math.min(...right.memberships.map((item) => item.authoritativeRank), 999);
        return leftRank - rightRank || left.player.name.localeCompare(right.player.name);
      });
  }, [position, query, records, report, sort, team]);

  const reset = () => {
    setQuery("");
    setTeam("ALL");
    setPosition("ALL");
    setReport("ALL");
    setSort("alphabetical");
  };

  return (
    <>
      <div className="directory-controls player-directory-controls" role="search">
        <label className="directory-search-wide">
          <span>Search players</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Player name" />
        </label>
        <Filter label="Team" value={team} onChange={setTeam} options={["ALL", ...teams]} />
        <Filter label="Position" value={position} onChange={(value) => setPosition(value as PlayerPosition | "ALL")} options={["ALL", "RB", "WR", "TE"]} />
        <Filter
          label="Report"
          value={report}
          onChange={(value) => setReport(value as ReportFamily | "ALL")}
          options={["ALL", "backfield_control", "target_hierarchy", "role_movement"]}
          labels={{ backfield_control: "Backfield Control", target_hierarchy: "Target Hierarchy", role_movement: "Role Movement" }}
        />
        <Filter label="Order" value={sort} onChange={(value) => setSort(value as typeof sort)} options={["alphabetical", "authority"]} labels={{ alphabetical: "Alphabetical", authority: "Supplied authority" }} />
      </div>

      {filtered.length ? (
        <div className="player-directory-list">
          {filtered.map((record) => (
            <article key={record.player.id}>
              <PlayerMonogram player={record.player} />
              <div className="player-directory-identity">
                <Link href={record.player.href}>{record.player.name}</Link>
                <span>{record.player.team} · {record.player.position}</span>
              </div>
              <div className="player-memberships">
                {record.memberships.length ? record.memberships.map((item) => <span key={item.family}>{item.label}</span>) : <span>Supplied identity</span>}
              </div>
              {record.currentEvidence ? <ShareEvidence evidence={record.currentEvidence} compact /> : <p className="no-current-evidence">No current share supplied</p>}
              <div className="player-directory-movement">
                <span>Latest movement</span>
                <strong>
                  {record.latestMovement
                    ? `${record.latestMovement.movement.percentagePointChange > 0 ? "+" : ""}${record.latestMovement.movement.percentagePointChange.toFixed(1)} pp`
                    : "Not supplied"}
                </strong>
              </div>
              <Link className="directory-action" href={record.player.href}>Open dossier <span aria-hidden="true">→</span></Link>
            </article>
          ))}
        </div>
      ) : (
        <section className="directory-empty" role="status">
          <p className="identity-eyebrow">No matching filters</p>
          <h2>No players match the current directory view</h2>
          <p>Reset the supplied identity filters to return to the full directory.</p>
          <button type="button" onClick={reset}>Reset player filters</button>
        </section>
      )}
    </>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
  labels = {},
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
  labels?: Record<string, string>;
}) {
  return (
    <label>
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{labels[option] ?? (option === "ALL" ? "All" : option)}</option>)}
      </select>
    </label>
  );
}
