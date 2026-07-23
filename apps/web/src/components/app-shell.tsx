import Link from "next/link";
import type { ReactNode } from "react";

const navItems = [
  ["/", "Feed"],
  ["/reports", "Reports"],
  ["/teams", "Teams"],
  ["/players", "Players"],
  ["/methodology", "Methodology"],
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link href="/" className="brand" aria-label="DepthSnap home">
          <span className="brand-mark" aria-hidden="true">DS</span>
          <span>
            <strong>DepthSnap</strong>
            <small>NFL role intelligence</small>
          </span>
        </Link>

        <nav className="desktop-nav" aria-label="Primary navigation">
          {navItems.map(([href, label]) => (
            <Link key={href} href={href}>{label}</Link>
          ))}
        </nav>

        <Link className="search-trigger" href="/search" aria-label="Search players and teams">
          <span aria-hidden="true">⌕</span>
          <span>Search</span>
        </Link>
      </header>

      <main>{children}</main>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        {navItems.slice(0, 4).map(([href, label]) => (
          <Link key={href} href={href}>{label}</Link>
        ))}
      </nav>
    </div>
  );
}
