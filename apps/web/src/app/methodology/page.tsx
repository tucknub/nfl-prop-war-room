import Link from "next/link";
import { ContractFailure } from "@/components/contract-failure";
import { FixtureNotice } from "@/components/fixture-notice";
import { loadStatusData } from "@/lib/data-loader";

export const dynamic = "force-dynamic";

const sections = [
  {
    id: "measures",
    kicker: "Scope",
    title: "What DepthSnap measures",
    body: (
      <>
        <p>
          DepthSnap describes documented RB opportunities and WR/TE targets
          from supplied role evidence. It keeps the player count attached to
          the matching team denominator so a share can always be audited.
        </p>
        <p>
          The Python pipeline remains the authority for membership, order,
          classifications, comparison periods, and publication. The web
          application validates and presents those supplied values.
        </p>
      </>
    ),
  },
  {
    id: "report-families",
    kicker: "Three report families",
    title: "Three questions, one evidence grammar",
    body: (
      <div className="method-report-grid">
        <article>
          <span>01</span>
          <h3>Backfield Control</h3>
          <p>
            Who owns each team’s documented RB opportunities? Each result
            pairs the player opportunity count with the matching team RB
            opportunity total.
          </p>
          <Link href="/reports/backfield">Open report</Link>
        </article>
        <article>
          <span>02</span>
          <h3>Target Hierarchy</h3>
          <p>
            Who owns each team’s documented WR and TE targets? Each result
            pairs player targets with the supplied team target total.
          </p>
          <Link href="/reports/targets">Open report</Link>
        </article>
        <article>
          <span>03</span>
          <h3>Role Movement</h3>
          <p>
            Whose documented role changed between two supplied periods?
            Previous and current counts stay visible beside the
            percentage-point change.
          </p>
          <Link href="/reports/movement">Open report</Link>
        </article>
      </div>
    ),
  },
  {
    id: "share",
    kicker: "Exact evidence",
    title: "Numerator, denominator, and share",
    body: (
      <div className="method-equation">
        <div>
          <span>Player count</span>
          <strong>Numerator</strong>
          <p>The supplied player opportunities, carries, or targets.</p>
        </div>
        <b aria-hidden="true">÷</b>
        <div>
          <span>Matching team total</span>
          <strong>Denominator</strong>
          <p>The supplied team universe for that same report and period.</p>
        </div>
        <b aria-hidden="true">=</b>
        <div>
          <span>Documented portion</span>
          <strong>Share</strong>
          <p>The supplied ratio, validated against the two raw counts.</p>
        </div>
      </div>
    ),
  },
  {
    id: "glossary",
    kicker: "Evidence glossary",
    title: "The evidence terms used throughout DepthSnap",
    body: (
      <dl className="evidence-glossary">
        <div>
          <dt>Numerator</dt>
          <dd>The supplied player count for the selected evidence period.</dd>
        </div>
        <div>
          <dt>Denominator</dt>
          <dd>The matching supplied team total for the same role and period.</dd>
        </div>
        <div>
          <dt>Share</dt>
          <dd>
            The supplied decimal ratio, displayed as a percentage and validated
            against the numerator and denominator.
          </dd>
        </div>
        <div>
          <dt>Percentage-point change</dt>
          <dd>
            Current share minus prior share, expressed in percentage points.
          </dd>
        </div>
        <div>
          <dt>Authoritative all-play evidence</dt>
          <dd>
            The Python-supplied result used for public report membership,
            ordering, and findings.
          </dd>
        </div>
        <div>
          <dt>Typical-game context</dt>
          <dd>
            Optional supporting evidence that never replaces the authoritative
            all-play result.
          </dd>
        </div>
        <div>
          <dt>Published through week</dt>
          <dd>
            The latest consecutive completed week admitted by the supplied
            publication result.
          </dd>
        </div>
      </dl>
    ),
  },
  {
    id: "authority",
    kicker: "Authority and context",
    title: "All-play evidence leads; typical-game context supports",
    body: (
      <>
        <p>
          All-play evidence is the authoritative public result. When the
          bundle supplies normal-game or typical-game context, DepthSnap labels
          it as supporting evidence rather than substituting it for the
          all-play value.
        </p>
        <p>
          Supporting context may be unavailable even when the authoritative
          result is complete. The closed data-quality label communicates that
          distinction.
        </p>
      </>
    ),
  },
  {
    id: "movement",
    kicker: "Period comparison",
    title: "Current, prior, and percentage-point movement",
    body: (
      <>
        <p>
          Role Movement compares two periods supplied by the authority bundle.
          Both raw numerators and denominators remain visible. Percentage-point
          movement is the current share minus the prior share, expressed in
          percentage points.
        </p>
        <p>
          Direction describes the documented change only. It does not assign
          cause, project a future role, or make a recommendation.
        </p>
      </>
    ),
  },
  {
    id: "publication",
    kicker: "Publication gate",
    title: "A week publishes only after the operational checks pass",
    body: (
      <div className="method-check-list">
        <div>
          <strong>Completed-week gate</strong>
          <p>
            Only consecutive, fully completed regular-season weeks are
            admitted. A completed week also requires the supplied schedule,
            play-by-play, and snap inputs expected by the Python pipeline.
          </p>
        </div>
        <div>
          <strong>Identity and snap coverage</strong>
          <p>
            Player opportunities must resolve to stable identities, and the
            required report-position snap coverage must clear the operational
            publication checks.
          </p>
        </div>
        <div>
          <strong>Partial-game handling</strong>
          <p>
            Current-season injury data is not treated as an authority. A
            partial game can be marked only through a reviewed manual override;
            otherwise that limitation remains explicit.
          </p>
        </div>
      </div>
    ),
  },
  {
    id: "quality",
    kicker: "Closed labels",
    title: "Data quality has three supplied states",
    body: (
      <dl className="quality-definitions">
        <div>
          <dt>Complete</dt>
          <dd>The supplied evidence passed the applicable publication checks.</dd>
        </div>
        <div>
          <dt>Reviewed partial game</dt>
          <dd>A reviewed manual partial-game designation accompanies the row.</dd>
        </div>
        <div>
          <dt>Unavailable supporting context</dt>
          <dd>
            The authoritative evidence may be present while optional supporting
            context is not supplied.
          </dd>
        </div>
      </dl>
    ),
  },
  {
    id: "limits",
    kicker: "Evidence, not advice",
    title: "Descriptive by design",
    body: (
      <>
        <p>
          DepthSnap does not predict outcomes, infer injuries or coaching
          intent, or provide betting, fantasy, lineup, or roster advice. It
          presents documented role evidence and the supplied limitations around
          that evidence.
        </p>
        <p>
          Review the current publication, hashes, checks, and limitations on
          Data Status.
        </p>
        <Link className="method-status-link" href="/data-status">
          Open Data Status
        </Link>
      </>
    ),
  },
] as const;

export default async function MethodologyPage() {
  const result = await loadStatusData();
  if (!result.ok) {
    return (
      <div className="page-shell methodology-page">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const status = result.data;
  return (
    <div className="page-shell methodology-page">
      {status.dataMode === "fixture" ? (
        <FixtureNotice>{status.dataNotice}</FixtureNotice>
      ) : null}
      <header className="methodology-hero">
        <div>
          <span className="section-kicker">Methodology</span>
          <h1>Read the count before the share.</h1>
          <p>
            A plain-language guide to what the supplied evidence means, what
            publishes, and where DepthSnap deliberately stops.
          </p>
        </div>
        <dl>
          <div>
            <dt>Authority</dt>
            <dd>Python role pipeline</dd>
          </div>
          <div>
            <dt>Public mode</dt>
            <dd>{status.dataMode}</dd>
          </div>
          <div>
            <dt>Scope</dt>
            <dd>Descriptive evidence</dd>
          </div>
        </dl>
      </header>

      <nav className="methodology-index" aria-label="Methodology sections">
        {sections.map((section, index) => (
          <a key={section.id} href={`#${section.id}`}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {section.kicker}
          </a>
        ))}
      </nav>

      <article className="methodology-content">
        {sections.map((section) => (
          <section key={section.id} id={section.id}>
            <span>{section.kicker}</span>
            <h2>{section.title}</h2>
            <div>{section.body}</div>
          </section>
        ))}
      </article>
    </div>
  );
}
