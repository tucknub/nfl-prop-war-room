import Link from "next/link";

export default function PlayerNotFound() {
  return (
    <div className="page-shell identity-page-shell">
      <section className="identity-state identity-not-found">
        <span className="identity-state-mark" aria-hidden="true">?</span>
        <p className="identity-eyebrow">Player not found</p>
        <h1>This player identity is not in the selected bundle</h1>
        <p>Use the player directory or global search to open a stable supplied identity.</p>
        <div className="identity-state-actions">
          <Link href="/players">Open Players</Link>
          <Link href="/search?focus=1">Search identities</Link>
        </div>
      </section>
    </div>
  );
}
