import Link from "next/link";
import {
  HierarchySection,
  IdentityPageHeader,
  IdentityState,
  MovementList,
  PlayerMonogram,
  ShareEvidence,
  TeamMonogram,
} from "@/components/identity-primitives";
import { WeeklyTimeline } from "@/components/weekly-timeline";
import type { PlayerEvidenceBundle } from "@/lib/identity-types";

export function PlayerDossier({ bundle }: { bundle: PlayerEvidenceBundle }) {
  if (bundle.status !== "published") {
    return (
      <div className="page-shell identity-page-shell">
        <IdentityPageHeader
          eyebrow="Player dossier"
          title={bundle.player.name}
          description="Supplied role evidence across the selected season."
          dataNotice={bundle.dataNotice}
          dataMode={bundle.dataMode}
          meta={`${bundle.season}${bundle.throughWeek ? ` · through Week ${bundle.throughWeek}` : " · no published week"}`}
        />
        <IdentityState status={bundle.status} subject={bundle.player.name} />
      </div>
    );
  }

  return (
    <div className="page-shell identity-page-shell dossier-page player-dossier-page">
      <IdentityPageHeader
        eyebrow="Player dossier"
        title={bundle.player.name}
        description="The supplied season story for this player’s documented role."
        dataNotice={bundle.dataNotice}
        dataMode={bundle.dataMode}
        meta={`${bundle.season}${bundle.throughWeek ? ` · through Week ${bundle.throughWeek}` : " · no published week"}`}
      >
        <nav className="dossier-report-links" aria-label={`${bundle.player.name} evidence links`}>
          <Link href={bundle.currentTeam.href}>Team dossier</Link>
          {bundle.reportMemberships.map((membership) => <Link key={membership.family} href={membership.href}>{membership.label}</Link>)}
        </nav>
      </IdentityPageHeader>

      <section className="player-identity-hero">
        <PlayerMonogram player={bundle.player} />
        <div className="player-identity-copy">
          <span>{bundle.currentTeam.id} · {bundle.player.position}</span>
          {bundle.suppliedRoleDescription ? (
            <h2>{bundle.suppliedRoleDescription}</h2>
          ) : null}
          <Link href={bundle.currentTeam.href}>
            <TeamMonogram team={bundle.currentTeam} size="small" />
            {bundle.currentTeam.name} <span aria-hidden="true">→</span>
          </Link>
        </div>
        {bundle.currentEvidence ? (
          <div className="player-current-evidence">
            <span>Current supplied evidence</span>
            <ShareEvidence evidence={bundle.currentEvidence} />
            {bundle.supportingContext ? (
              <p>Supporting context: {bundle.supportingContext.label} · {bundle.supportingContext.evidence.numerator} of {bundle.supportingContext.evidence.denominator} · {(bundle.supportingContext.evidence.share * 100).toFixed(1)}%</p>
            ) : null}
          </div>
        ) : (
          <p className="identity-inline-empty">No current hierarchy evidence supplied.</p>
        )}
        {bundle.latestMovement ? (
          <div className={`player-latest-movement movement-change-${bundle.latestMovement.direction}`}>
            <span>Latest supplied movement</span>
            <strong>{bundle.latestMovement.movement.percentagePointChange > 0 ? "+" : ""}{bundle.latestMovement.movement.percentagePointChange.toFixed(1)} pp</strong>
            <p>{bundle.latestMovement.finding}</p>
          </div>
        ) : null}
      </section>

      <WeeklyTimeline points={bundle.weeklyEvidence} playerName={bundle.player.name} />

      <div className="player-dossier-grid">
        <section className="dossier-section membership-section">
          <header><div><p className="identity-eyebrow">Supplied membership</p><h2>Current reports</h2></div></header>
          {bundle.reportMemberships.length ? (
            <div>
              {bundle.reportMemberships.map((membership) => (
                <Link href={membership.href} key={membership.family}>
                  <span>{membership.label}</span>
                  <strong>Authority rank {membership.authoritativeRank}</strong>
                  <i aria-hidden="true">→</i>
                </Link>
              ))}
            </div>
          ) : <p className="identity-inline-empty">No current report membership supplied.</p>}
        </section>
        <HierarchySection title="Team hierarchy context" description={`Nearby supplied ${bundle.player.position} evidence for the evidence team.`} rows={bundle.teamHierarchyContext} />
      </div>

      <MovementList movements={bundle.movementHistory} title="Movement history" />

      <footer className="dossier-quality">
        <div><span>Identity</span><strong>Team-neutral player ID</strong></div>
        <div><span>Generated</span><strong>{new Date(bundle.generatedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}</strong></div>
        <div><span>Source</span><strong>{bundle.sourceVersion}</strong></div>
        <Link href="/methodology">Read Methodology →</Link>
      </footer>
    </div>
  );
}
