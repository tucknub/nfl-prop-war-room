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
      <label htmlFor="global-identity-search">Search supplied identities</label>
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
        <span>{query ? `${results.length} matching identities` : "Supplied identities"}</span>
        <span>Teams and players only</span>
      </div>
      {results.length ? (
        <ul id="identity-search-results" role="listbox">
          {results.map((result, indexValue) => (
            <li
              id={result.id}
              key={result.id}
              role="option"
              aria-selected={indexValue === activeIndex}
              onMouseEnter={() => setActiveIndex(indexValue)}
            >
              <Link href={result.href}>
                <span className={`search-result-type search-result-${result.type}`}>{result.type === "player" ? "P" : "T"}</span>
                <span className="search-result-copy">
                  <strong>{result.displayName}</strong>
                  <small>{result.secondaryLabel}</small>
                </span>
                <span className="search-result-evidence">{result.summary}</span>
                <span aria-hidden="true">→</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <section className="directory-empty" role="status">
          <p className="identity-eyebrow">No matching identities</p>
          <h2>No teams or players match “{query}”</h2>
          <p>Try a supplied name, abbreviation, or alias.</p>
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
