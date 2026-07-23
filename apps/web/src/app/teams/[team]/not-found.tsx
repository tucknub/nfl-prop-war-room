import Link from "next/link";

export default function TeamNotFound() {
  return (
    <div className="page-shell identity-page-shell">
      <section className="identity-state identity-not-found">
        <span className="identity-state-mark" aria-hidden="true">?</span>
        <p className="identity-eyebrow">Team not found</p>
        <h1>This team identity is not in the fixture bundle</h1>
        <p>Use the team directory or global search to open a stable supplied identity.</p>
        <div className="identity-state-actions">
          <Link href="/teams">Open Teams</Link>
          <Link href="/search?focus=1">Search identities</Link>
        </div>
      </section>
    </div>
  );
}
