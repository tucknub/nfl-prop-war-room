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
import {
  formatPercent,
  formatPoints,
  movementLabel,
} from "@/lib/consumer-presentation";
import type { PlayerEvidenceBundle } from "@/lib/identity-types";

export function PlayerDossier({
  bundle,
  comparisonByRecord = {},
}: {
  bundle: PlayerEvidenceBundle;
  comparisonByRecord?: Readonly<Record<string, string>>;
}) {
  if (bundle.status !== "published") {
    return (
      <div className="page-shell identity-page-shell">
        <IdentityPageHeader
          eyebrow="Player dossier"
          title={bundle.player.name}
          description="Current and recent documented role evidence."
          dataNotice={bundle.dataNotice}
          dataMode={bundle.dataMode}
          meta={`${bundle.season}${bundle.throughWeek ? ` · through Week ${bundle.throughWeek}` : " · no published week"}`}
        />
        <IdentityState status={bundle.status} subject={bundle.player.name} />
      </div>
    );
  }

  const currentRole =
    bundle.currentRoleLabel ?? "No recent qualifying report";
  const currentHierarchy = bundle.teamHierarchyContext.filter(
    (row) =>
      (!bundle.currentRoleFamily ||
        row.roleFamily === bundle.currentRoleFamily) &&
      (!bundle.currentEvidence ||
        row.evidence.opportunityLabel ===
          bundle.currentEvidence.opportunityLabel),
  );
  const teamPosition =
    currentHierarchy.findIndex((row) => row.player.id === bundle.player.id) + 1;
  const latest = bundle.latestMovement;

  return (
    <div className="page-shell identity-page-shell dossier-page player-dossier-page">
      <IdentityPageHeader
        eyebrow="Player dossier"
        title={bundle.player.name}
        description={`${bundle.player.position} role evidence for ${bundle.currentTeam.name}, updated through Week ${bundle.throughWeek}.`}
        dataNotice={bundle.dataNotice}
        dataMode={bundle.dataMode}
        meta={`${bundle.season} · through Week ${bundle.throughWeek}`}
      >
        <nav
          className="dossier-report-links"
          aria-label={`${bundle.player.name} evidence links`}
        >
          <Link href={bundle.currentTeam.href}>View team dossier</Link>
          {bundle.reportMemberships.map((membership) => (
            <Link key={membership.family} href={membership.href}>
              {membership.label}
            </Link>
          ))}
        </nav>
      </IdentityPageHeader>

      <section className="player-identity-hero">
        <PlayerMonogram player={bundle.player} />
        <div className="player-identity-copy">
          <span>
            {bundle.player.position} · {bundle.currentTeam.name}
          </span>
          <h2>{currentRole}</h2>
          <Link href={bundle.currentTeam.href}>
            <TeamMonogram team={bundle.currentTeam} size="small" />
            {bundle.currentTeam.name} <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="player-hero-summary">
          {bundle.currentEvidence ? (
            <>
              <span>Current role</span>
              <ShareEvidence evidence={bundle.currentEvidence} />
            </>
          ) : (
            <p className="identity-inline-empty">
              No recent qualifying report.
            </p>
          )}
        </div>
      </section>

      <section
        className="player-summary-cards"
        aria-label={`${bundle.player.name} role summary`}
      >
        <article>
          <span>Current role</span>
          <h2>{currentRole}</h2>
          {bundle.currentEvidence ? (
            <p>
              {formatPercent(bundle.currentEvidence.share)} ·{" "}
              {bundle.currentEvidence.numerator} of{" "}
              {bundle.currentEvidence.denominator}{" "}
              {bundle.currentEvidence.opportunityLabel}
            </p>
          ) : (
            <p>No current role evidence.</p>
          )}
        </article>
        <article
          className={
            latest ? `summary-movement-${latest.direction}` : undefined
          }
        >
          <span>Recent change</span>
          {latest ? (
            <>
              <h2>
                {movementLabel(latest.movement.percentagePointChange)} ·{" "}
                {formatPoints(latest.movement.percentagePointChange)}
              </h2>
              <p>
                {formatPercent(latest.movement.previous.share)} (
                {latest.movement.previous.numerator}/
                {latest.movement.previous.denominator}) →{" "}
                {formatPercent(latest.movement.current.share)} (
                {latest.movement.current.numerator}/
                {latest.movement.current.denominator})
              </p>
            </>
          ) : (
            <>
              <h2>Stable</h2>
              <p>No recent qualifying movement.</p>
            </>
          )}
        </article>
        <article>
          <span>Team position</span>
          <h2>
            {teamPosition > 0
              ? `${teamPosition} of ${currentHierarchy.length}`
              : "Not listed"}
          </h2>
          <p>
            {teamPosition > 0
              ? `${currentRole} among ${bundle.currentTeam.name} teammates`
              : "No matching team hierarchy row"}
          </p>
        </article>
      </section>

      <WeeklyTimeline
        points={bundle.weeklyEvidence}
        playerName={bundle.player.name}
        throughWeek={bundle.throughWeek}
        primaryRoleFamily={bundle.currentRoleFamily}
      />

      <HierarchySection
        title="Teammate comparison"
        description={`Compare ${bundle.player.name} with nearby ${bundle.currentTeam.name} teammates, one metric at a time.`}
        rows={bundle.teamHierarchyContext}
      />

      <MovementList
        movements={bundle.movementHistory}
        title="Movement history"
        comparisonByRecord={comparisonByRecord}
      />

      <details className="dossier-technical-details technical-details">
        <summary>Technical details</summary>
        <div className="dossier-quality">
          <div>
            <span>Player reference</span>
            <strong>Team-neutral player ID · {bundle.player.id}</strong>
          </div>
          <div>
            <span>Generated</span>
            <strong>
              {new Date(bundle.generatedAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
                timeZone: "UTC",
              })}
            </strong>
          </div>
          <div>
            <span>Source version</span>
            <strong>{bundle.sourceVersion}</strong>
          </div>
          <Link href="/methodology">Read Methodology →</Link>
        </div>
      </details>
    </div>
  );
}
