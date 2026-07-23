import Link from "next/link";
import type { ReactNode } from "react";
import { SearchIcon, StatusIcon } from "@/components/icons";
import {
  DesktopNavigation,
  MobileNavigation,
} from "@/components/navigation";
import { GlobalSearchShortcut } from "@/components/global-search-shortcut";
import { loadStatusData } from "@/lib/data-loader";

export async function AppShell({ children }: { children: ReactNode }) {
  const statusResult = await loadStatusData();
  const status = statusResult.ok ? statusResult.data : null;
  const freshnessLabel =
    status?.status === "published" && status.throughWeek
      ? `${status.season} · Week ${status.throughWeek}`
      : status?.status === "no_published_week"
        ? `${status.season} · No published week`
        : "Data unavailable";
  const modeLabel = status
    ? status.dataMode === "fixture"
      ? "Design fixture"
      : "Validated export"
    : "Contract check";
  return (
    <div className="app-shell">
      <GlobalSearchShortcut />
      <a className="skip-link" href="#main-content">
        Skip to findings
      </a>

      <header className="site-header">
        <div className="header-inner">
          <Link href="/" className="brand" aria-label="DepthSnap home">
            <span className="brand-symbol" aria-hidden="true">
              D
            </span>
            <span className="brand-copy">
              <span className="brand-name">
                Depth<span>Snap</span>
              </span>
              <small>NFL Role Intelligence</small>
            </span>
          </Link>

          <DesktopNavigation />

          <div className="header-tools">
            <Link
              className="search-trigger"
              href="/search?focus=1"
              aria-label="Search players and teams"
            >
              <SearchIcon />
              <span>Search players or teams</span>
              <kbd>/</kbd>
            </Link>
            <div
              className="freshness-indicator"
              aria-label={`${modeLabel}: ${freshnessLabel}`}
            >
              <StatusIcon />
              <span>
                <strong>{freshnessLabel}</strong>
                <small>{modeLabel}</small>
              </span>
            </div>
          </div>
        </div>
      </header>

      <main id="main-content">{children}</main>

      <MobileNavigation />
    </div>
  );
}
