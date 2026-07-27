"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SearchIdentity } from "@/lib/identity-types";

export function SearchExperience({
  index,
  initialQuery = "",
  shouldFocus = false,
}: {
  index: readonly SearchIdentity[];
  initialQuery?: string;
  shouldFocus?: boolean;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState(initialQuery);
  const [activeIndex, setActiveIndex] = useState(0);
  const results = useMemo(() => rankResults(index, query), [index, query]);
  const teamNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const record of index) {
      if (record.type !== "team") continue;
      const abbreviation = record.secondaryLabel.split("·").at(-1)?.trim();
      if (abbreviation) names.set(abbreviation, record.displayName);
    }
    return names;
  }, [index]);

  useEffect(() => {
    if (shouldFocus || window.innerWidth < 720) {
      inputRef.current?.focus();
    }
  }, [shouldFocus]);

  useEffect(() => setActiveIndex(0), [query]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((value) => Math.min(value + 1, Math.max(results.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && results[activeIndex]) {
      event.preventDefault();
      router.push(results[activeIndex].href);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setQuery("");
    }
  };

  return (
    <div className="global-search">
      <label htmlFor="global-identity-search">Search players and teams</label>
      <div className="global-search-input">
        <span aria-hidden="true">⌕</span>
        <input
          ref={inputRef}
          id="global-identity-search"
          type="search"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="identity-search-results"
          aria-activedescendant={results[activeIndex]?.id}
          aria-autocomplete="list"
          placeholder="Search players or teams"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
        />
        {query ? <button type="button" onClick={() => setQuery("")}>Clear</button> : <kbd>/</kbd>}
      </div>
      <p className="search-help">Exact and prefix matches appear first. Use ↑ ↓ and Enter to navigate.</p>
      <div className="search-result-heading">
        <span>{query ? `${results.length} results` : "Players and teams"}</span>
        <span>Teams and players only</span>
      </div>
      {results.length ? (
        <ul id="identity-search-results" role="listbox">
          {results.map((result, indexValue) => {
            const abbreviation = result.secondaryLabel
              .split("·")
              .at(-1)
              ?.trim();
            const position = result.secondaryLabel.split("·")[0]?.trim();
            const secondary =
              result.type === "player"
                ? `${position} · ${teamNames.get(abbreviation ?? "") ?? abbreviation ?? "Team unavailable"}`
                : abbreviation ?? result.secondaryLabel;
            const noRecentReport = /no default-report|stable player identity/i.test(
              result.summary,
            );
            return (
            <li
              id={result.id}
              key={result.id}
              role="option"
              aria-selected={indexValue === activeIndex}
              onMouseEnter={() => setActiveIndex(indexValue)}
            >
              <Link
                href={result.href}
                aria-label={`${result.displayName}, view ${result.type}`}
              >
                <span className={`search-result-type search-result-${result.type}`}>{result.type === "player" ? "P" : "T"}</span>
                <span className="search-result-copy">
                  <strong>{result.displayName}</strong>
                  <small>{secondary}</small>
                </span>
                <span className="search-result-evidence">
                  {noRecentReport
                    ? "No recent qualifying report"
                    : result.type === "player"
                      ? result.summary
                      : result.summary}
                </span>
                <span className="search-result-action">
                  {result.type === "player" ? "View player" : "View team"}
                  <span aria-hidden="true"> →</span>
                </span>
              </Link>
            </li>
            );
          })}
        </ul>
      ) : (
        <section className="directory-empty" role="status">
          <p className="identity-eyebrow">No matching players or teams</p>
          <h2>No teams or players match “{query}”</h2>
          <p>Try a player name, team name, or abbreviation.</p>
          <button type="button" onClick={() => setQuery("")}>Clear search</button>
        </section>
      )}
    </div>
  );
}

function rankResults(
  index: readonly SearchIdentity[],
  query: string,
): readonly SearchIdentity[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return index.slice(0, 10);
  const matchScore = (item: SearchIdentity) => {
    const values = [item.displayName, ...item.searchAliases].map((value) => value.toLowerCase());
    if (values.some((value) => value === normalized)) return 0;
    if (values.some((value) => value.startsWith(normalized))) return 1;
    if (values.some((value) => value.includes(normalized))) return 2;
    return 3;
  };
  return index
    .filter((item) => matchScore(item) < 3)
    .toSorted((left, right) => matchScore(left) - matchScore(right) || left.displayName.localeCompare(right.displayName))
    .slice(0, 14);
}
