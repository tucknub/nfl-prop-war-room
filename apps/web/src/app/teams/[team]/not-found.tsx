import Link from "next/link";

export default function TeamNotFound() {
  return (
    <div className="page-shell identity-page-shell">
      <section className="identity-state identity-not-found">
        <span className="identity-state-mark" aria-hidden="true">?</span>
        <p className="identity-eyebrow">Team not found</p>
        <h1>This team is not available</h1>
        <p>Use the team directory or search to find another team.</p>
        <div className="identity-state-actions">
          <Link href="/teams">Open Teams</Link>
          <Link href="/search?focus=1">Search players and teams</Link>
        </div>
      </section>
    </div>
  );
}
