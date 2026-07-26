import Link from "next/link";
import {
  HierarchySection,
  IdentityPageHeader,
  IdentityState,
  MovementList,
  ShareEvidence,
  TeamMonogram,
} from "@/components/identity-primitives";
import { possessiveName } from "@/lib/consumer-presentation";
import type { TeamEvidenceBundle } from "@/lib/identity-types";

export function TeamDossier({
  bundle,
  comparisonByRecord = {},
}: {
  bundle: TeamEvidenceBundle;
  comparisonByRecord?: Readonly<Record<string, string>>;
}) {
  if (bundle.status !== "published") {
    return (
      <div className="page-shell identity-page-shell">
        <IdentityPageHeader
          eyebrow="Team dossier"
          title={bundle.team.name}
          description="Current team role evidence."
          dataNotice={bundle.dataNotice}
          dataMode={bundle.dataMode}
          meta={`${bundle.season}${bundle.throughWeek ? ` · through Week ${bundle.throughWeek}` : " · no published week"}`}
        />
        <IdentityState status={bundle.status} subject={bundle.team.name} />
      </div>
    );
  }

  const backfield =
    bundle.backfieldHierarchy.find(
      (row) => row.evidence.opportunityLabel === "opportunities",
    ) ?? bundle.backfieldHierarchy[0];
  const wr = bundle.wrTargetHierarchy[0];
  const te = bundle.teTargetHierarchy[0];
  const gains = bundle.movements
    .filter((movement) => movement.movement.percentagePointChange > 0)
    .toSorted(
      (left, right) =>
        right.movement.percentagePointChange -
        left.movement.percentagePointChange,
    );
  const declines = bundle.movements
    .filter((movement) => movement.movement.percentagePointChange < 0)
    .toSorted(
      (left, right) =>
        left.movement.percentagePointChange -
        right.movement.percentagePointChange,
    );
  const highlightedMovements = [...gains.slice(0, 2), ...declines.slice(0, 2)];
  const summary = [
    backfield
      ? `${backfield.player.name} leads ${possessiveName(bundle.team.name)} backfield with ${backfield.evidence.numerator} of ${backfield.evidence.denominator} ${backfield.evidence.opportunityLabel}.`
      : null,
    wr
      ? `${wr.player.name} leads WR targets with ${wr.evidence.numerator} of ${wr.evidence.denominator}.`
      : null,
    te
      ? `${te.player.name} leads TE targets with ${te.evidence.numerator} of ${te.evidence.denominator}.`
      : null,
    gains[0]
      ? `${gains[0].player.name} has the largest displayed recent increase.`
      : declines[0]
        ? `${declines[0].player.name} has the largest displayed recent decline.`
        : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="page-shell identity-page-shell dossier-page">
      <IdentityPageHeader
        eyebrow="Team dossier"
        title={bundle.team.name}
        description={`Role leaders and recent changes, updated through Week ${bundle.throughWeek}.`}
        dataNotice={bundle.dataNotice}
        dataMode={bundle.dataMode}
        meta={`${bundle.season} · through Week ${bundle.throughWeek}`}
      >
        <nav
          className="dossier-report-links"
          aria-label={`${bundle.team.name} reports`}
        >
          <Link href={`/reports/backfield?team=${bundle.team.id}`}>
            Backfield
          </Link>
          <Link href={`/reports/targets?team=${bundle.team.id}`}>Targets</Link>
          <Link href={`/reports/movement?team=${bundle.team.id}`}>
            Movement
          </Link>
        </nav>
      </IdentityPageHeader>

      <section className="team-identity-hero">
        <TeamMonogram team={bundle.team} />
        <div>
          <span>{bundle.team.abbreviation}</span>
          <h2>Current role structure</h2>
          <p>
            {bundle.team.conference} · {bundle.team.division}
          </p>
        </div>
        {backfield ? (
          <div className="team-lead-evidence">
            <span>Backfield leader</span>
            <Link href={backfield.player.href}>{backfield.player.name}</Link>
            <ShareEvidence evidence={backfield.evidence} />
          </div>
        ) : null}
      </section>

      <p className="team-dossier-summary">{summary}</p>

      <MovementList
        movements={highlightedMovements}
        title="Biggest recent gains and declines"
        comparisonByRecord={comparisonByRecord}
      />

      <div className="dossier-hierarchy-grid">
        <HierarchySection
          title="Backfield hierarchy"
          description="Choose total opportunities or carries. Each player appears once per metric."
          rows={bundle.backfieldHierarchy}
        />
        <HierarchySection
          title="WR hierarchy"
          description="Wide receiver targets against the matching team total."
          rows={bundle.wrTargetHierarchy}
        />
        <HierarchySection
          title="TE hierarchy"
          description="Tight end targets against the matching team total."
          rows={bundle.teTargetHierarchy}
        />
      </div>

      <details className="dossier-deeper-evidence technical-details">
        <summary>View deeper evidence</summary>
        <section className="dossier-section linked-identities">
          <header>
            <div>
              <p className="identity-eyebrow">Player links</p>
              <h2>Players in this dossier</h2>
            </div>
            <Link
              className="text-action"
              href={`/players?team=${bundle.team.id}`}
            >
              Open player directory →
            </Link>
          </header>
          <div>
            {bundle.linkedPlayers.map((player) => (
              <Link href={player.href} key={player.id}>
                <strong>{player.name}</strong>
                <span>{player.position} · View player</span>
              </Link>
            ))}
          </div>
        </section>
        <div className="dossier-quality">
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
          <Link href="/data-status">Open Data Status →</Link>
        </div>
      </details>
    </div>
  );
}
