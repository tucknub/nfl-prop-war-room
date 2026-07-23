import Link from "next/link";
import {
  HierarchySection,
  IdentityPageHeader,
  IdentityState,
  MovementList,
  ShareEvidence,
  TeamMonogram,
} from "@/components/identity-primitives";
import type { TeamEvidenceBundle } from "@/lib/identity-types";

export function TeamDossier({ bundle }: { bundle: TeamEvidenceBundle }) {
  if (bundle.status !== "published") {
    return (
      <div className="page-shell identity-page-shell">
        <IdentityPageHeader
          eyebrow="Team dossier"
          title={bundle.team.name}
          description={bundle.suppliedSummary}
          fixtureNotice={bundle.fixtureNotice}
          meta={`${bundle.season} · through Week ${bundle.throughWeek}`}
        />
        <IdentityState status={bundle.status} subject={bundle.team.name} />
      </div>
    );
  }
  const lead = bundle.backfieldHierarchy[0] ?? bundle.wrTargetHierarchy[0] ?? bundle.teTargetHierarchy[0];

  return (
    <div className="page-shell identity-page-shell dossier-page">
      <IdentityPageHeader
        eyebrow="Team dossier"
        title={bundle.team.name}
        description={bundle.suppliedSummary}
        fixtureNotice={bundle.fixtureNotice}
        meta={`${bundle.season} · through Week ${bundle.throughWeek}`}
      >
        <nav className="dossier-report-links" aria-label={`${bundle.team.name} reports`}>
          <Link href={`/reports/backfield?team=${bundle.team.id}`}>Backfield</Link>
          <Link href={`/reports/targets?team=${bundle.team.id}`}>Targets</Link>
          <Link href={`/reports/movement?team=${bundle.team.id}`}>Movement</Link>
        </nav>
      </IdentityPageHeader>

      <section className="team-identity-hero">
        <TeamMonogram team={bundle.team} />
        <div>
          <span>{bundle.team.abbreviation}</span>
          <h2>Current role structure</h2>
          <p>{bundle.team.conference} · {bundle.team.division} · fixture identity</p>
        </div>
        {lead ? (
          <div className="team-lead-evidence">
            <span>Leading supplied role</span>
            <Link href={lead.player.href}>{lead.player.name}</Link>
            <ShareEvidence evidence={lead.evidence} />
          </div>
        ) : null}
      </section>

      <MovementList movements={bundle.movements.slice(0, 3)} />
      <div className="dossier-hierarchy-grid">
        <HierarchySection title="Backfield hierarchy" description="Documented RB opportunity shares." rows={bundle.backfieldHierarchy} />
        <HierarchySection title="WR target hierarchy" description="Documented WR targets against the matching team total." rows={bundle.wrTargetHierarchy} />
        <HierarchySection title="TE target hierarchy" description="Documented TE targets against the matching team total." rows={bundle.teTargetHierarchy} />
      </div>

      <section className="dossier-section linked-identities">
        <header>
          <div>
            <p className="identity-eyebrow">Identity navigation</p>
            <h2>Linked player evidence</h2>
          </div>
          <Link className="text-action" href={`/players?team=${bundle.team.id}`}>Open player directory →</Link>
        </header>
        <div>
          {bundle.linkedPlayers.map((player) => (
            <Link href={player.href} key={player.id}>
              <strong>{player.name}</strong>
              <span>{player.position} · {player.team}</span>
            </Link>
          ))}
        </div>
      </section>

      <footer className="dossier-quality">
        <div><span>Data quality</span><strong>{bundle.dataQuality.replaceAll("_", " ")}</strong></div>
        <div><span>Generated</span><strong>{new Date(bundle.generatedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}</strong></div>
        <div><span>Source</span><strong>{bundle.sourceVersion}</strong></div>
        <Link href="/data-status">Open Data Status →</Link>
      </footer>
    </div>
  );
}
