import Link from "next/link";
import { FixtureNotice } from "@/components/fixture-notice";
import type {
  CanonicalPlayerIdentity,
  HierarchyEvidenceRow,
  IdentityBundleStatus,
  SuppliedMovementRecord,
  TeamIdentity,
} from "@/lib/identity-types";
import type { RawShareEvidence } from "@/lib/types";

export function IdentityPageHeader({
  eyebrow,
  title,
  description,
  dataNotice,
  dataMode,
  meta,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  dataNotice: string;
  dataMode?: "fixture" | "export";
  meta: string;
  children?: React.ReactNode;
}) {
  return (
    <>
      {dataMode === "fixture" ? (
        <FixtureNotice>{dataNotice}</FixtureNotice>
      ) : null}
      <header className="identity-page-header">
        <div>
          <p className="identity-eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="identity-header-meta">
          <span>{dataMode === "export" ? "Export status" : "Fixture status"}</span>
          <strong>{meta}</strong>
        </div>
        {children}
      </header>
    </>
  );
}

export function IdentityState({
  status,
  subject,
}: {
  status: Exclude<IdentityBundleStatus, "published">;
  subject: string;
}) {
  const unpublished = status === "no_published_week";
  return (
    <section className="identity-state" role="status">
      <span className="identity-state-mark" aria-hidden="true">
        {unpublished ? "—" : "!"}
      </span>
      <p className="identity-eyebrow">{unpublished ? "Publishing state" : "Bundle state"}</p>
      <h2>
        {unpublished
          ? `No completed week is published for ${subject}`
          : `${subject} evidence is unavailable`}
      </h2>
      <p>
        {unpublished
          ? "A completed validated week has not been published. No estimated shares are shown."
          : "The selected bundle could not be read. No stale or fabricated evidence is shown."}
      </p>
      <div className="identity-state-actions">
        <Link href="/data-status">Open Data Status</Link>
        <Link href="/methodology">Publishing explanation</Link>
      </div>
    </section>
  );
}

export function TeamMonogram({ team, size = "large" }: { team: TeamIdentity; size?: "small" | "large" }) {
  return (
    <span
      className={`team-monogram team-monogram-${size} team-monogram-${team.accent}`}
      aria-hidden="true"
    >
      {team.monogram}
    </span>
  );
}

export function PlayerMonogram({ player }: { player: CanonicalPlayerIdentity }) {
  return (
    <span className="player-monogram" aria-hidden="true">
      {player.name
        .split(" ")
        .map((part) => part[0])
        .join("")}
    </span>
  );
}

export function ShareEvidence({
  evidence,
  compact = false,
}: {
  evidence: RawShareEvidence;
  compact?: boolean;
}) {
  const percent = (evidence.share * 100).toFixed(1);
  return (
    <div
      className={`identity-share ${compact ? "identity-share-compact" : ""}`}
      aria-label={`${percent} percent, ${evidence.numerator} of ${evidence.denominator} ${evidence.opportunityLabel}`}
    >
      <div className="identity-share-value">
        <strong>{percent}%</strong>
        <span>
          {evidence.numerator} of {evidence.denominator} {evidence.opportunityLabel}
        </span>
      </div>
      <span className="identity-share-track" aria-hidden="true">
        <span style={{ width: `${Math.min(evidence.share * 100, 100)}%` }} />
      </span>
    </div>
  );
}

export function HierarchySection({
  title,
  description,
  rows,
}: {
  title: string;
  description: string;
  rows: readonly HierarchyEvidenceRow[];
}) {
  return (
    <section className="dossier-section hierarchy-section">
      <header>
        <div>
          <p className="identity-eyebrow">Supplied hierarchy</p>
          <h2>{title}</h2>
        </div>
        <p>{description}</p>
      </header>
      {rows.length ? (
        <ol className="hierarchy-list">
          {rows.map((row) => (
            <li key={row.player.id}>
              <span className="hierarchy-rank">{row.authoritativeOrder}</span>
              <div className="hierarchy-player">
                <Link href={row.player.href}>{row.player.name}</Link>
                <span>
                  {row.player.position} · {row.classificationLabel}
                </span>
              </div>
              <ShareEvidence evidence={row.evidence} />
              <Link className="text-action" href={row.player.href}>
                Player evidence <span aria-hidden="true">→</span>
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <p className="identity-inline-empty">No supplied hierarchy rows for this role family.</p>
      )}
    </section>
  );
}

export function MovementList({
  movements,
  title = "Biggest supplied movements",
}: {
  movements: readonly SuppliedMovementRecord[];
  title?: string;
}) {
  return (
    <section className="dossier-section movement-section">
      <header>
        <div>
          <p className="identity-eyebrow">Period comparison</p>
          <h2>{title}</h2>
        </div>
        <Link className="text-action" href="/reports/movement">
          Open Role Movement <span aria-hidden="true">→</span>
        </Link>
      </header>
      {movements.length ? (
        <div className="identity-movement-list">
          {movements.map((record) => {
            const change = record.movement.percentagePointChange;
            return (
              <article key={`${record.player.id}-${record.authoritativeOrder}`}>
                <div className="movement-identity">
                  <Link href={record.player.href}>{record.player.name}</Link>
                  <span>{record.player.position} · {record.roleFamily}</span>
                </div>
                <div className="movement-transition">
                  <ShareEvidence evidence={record.movement.previous} compact />
                  <span aria-hidden="true">→</span>
                  <ShareEvidence evidence={record.movement.current} compact />
                </div>
                <div className={`movement-change movement-change-${record.direction}`}>
                  <strong>{change > 0 ? "+" : ""}{change.toFixed(1)} pp</strong>
                  <span>{record.direction === "gain" ? "Gain" : record.direction === "decline" ? "Decline" : "Stable"}</span>
                </div>
                <p>{record.finding}</p>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="identity-inline-empty">No supplied movement records for this identity.</p>
      )}
    </section>
  );
}

export function IdentityLoading({ title }: { title: string }) {
  return (
    <div className="page-shell identity-page-shell" aria-busy="true" aria-label={`Loading ${title}`}>
      <div className="fixture-notice skeleton skeleton-notice" />
      <div className="identity-loading-header skeleton" />
      <div className="identity-loading-grid">
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
    </div>
  );
}
