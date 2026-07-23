"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ShareEvidence, TeamMonogram } from "@/components/identity-primitives";
import type { TeamDirectoryRecord } from "@/lib/identity-types";

export function TeamDirectory({
  records,
  initialQuery = "",
}: {
  records: readonly TeamDirectoryRecord[];
  initialQuery?: string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [sort, setSort] = useState<"alphabetical" | "movement">("alphabetical");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const result = records.filter((record) =>
      [
        record.team.name,
        record.team.abbreviation,
        ...record.team.searchAliases,
      ].some((value) => value.toLowerCase().includes(normalized)),
    );
    return result.toSorted((left, right) =>
      sort === "alphabetical"
        ? left.team.name.localeCompare(right.team.name)
        : Math.abs(right.largestMovement?.movement.percentagePointChange ?? 0) -
          Math.abs(left.largestMovement?.movement.percentagePointChange ?? 0),
    );
  }, [query, records, sort]);

  return (
    <>
      <div className="directory-controls" role="search">
        <label>
          <span>Search teams</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Team name or abbreviation"
          />
        </label>
        <label>
          <span>Order</span>
          <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
            <option value="alphabetical">Alphabetical</option>
            <option value="movement">Largest supplied movement</option>
          </select>
        </label>
      </div>

      {filtered.length ? (
        <div className="team-directory-grid">
          {filtered.map((record) => (
            <article className="team-directory-item" key={record.team.id}>
              <header>
                <TeamMonogram team={record.team} />
                <div>
                  <span>{record.team.abbreviation}</span>
                  <h2>{record.team.name}</h2>
                  <p>{record.team.conference} · {record.team.division}</p>
                </div>
              </header>
              <div className="team-role-preview">
                <DirectoryEvidence label="Top RB" row={record.topBackfield} />
                <DirectoryEvidence label="Top WR" row={record.topWr} />
                <DirectoryEvidence label="Top TE" row={record.topTe} />
              </div>
              <div className="team-movement-preview">
                <span>Largest supplied movement</span>
                {record.largestMovement ? (
                  <strong className={`movement-text-${record.largestMovement.direction}`}>
                    {record.largestMovement.player.name} ·{" "}
                    {record.largestMovement.movement.percentagePointChange > 0 ? "+" : ""}
                    {record.largestMovement.movement.percentagePointChange.toFixed(1)} pp
                  </strong>
                ) : (
                  <strong>No supplied movement</strong>
                )}
              </div>
              <Link className="directory-action" href={record.team.href}>
                Open team dossier <span aria-hidden="true">→</span>
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <section className="directory-empty" role="status">
          <p className="identity-eyebrow">No matching filters</p>
          <h2>No supplied teams match “{query}”</h2>
          <p>Adjust the team search or reset it to see all supplied identities.</p>
          <button type="button" onClick={() => setQuery("")}>Reset team search</button>
        </section>
      )}
    </>
  );
}

function DirectoryEvidence({
  label,
  row,
}: {
  label: string;
  row: TeamDirectoryRecord["topBackfield"];
}) {
  return (
    <div>
      <span>{label}</span>
      {row ? (
        <>
          <strong>{row.player.name}</strong>
          <ShareEvidence evidence={row.evidence} compact />
        </>
      ) : (
        <em>Not supplied</em>
      )}
    </div>
  );
}
