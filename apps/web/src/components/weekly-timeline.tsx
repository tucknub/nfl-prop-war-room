import type { WeeklyEvidencePoint } from "@/lib/identity-types";

export function WeeklyTimeline({
  points,
  playerName,
}: {
  points: readonly WeeklyEvidencePoint[];
  playerName: string;
}) {
  return (
    <section className="dossier-section weekly-timeline" aria-labelledby="weekly-role-timeline">
      <header>
        <div>
          <p className="identity-eyebrow">Exact weekly evidence</p>
          <h2 id="weekly-role-timeline">Weekly role timeline</h2>
        </div>
        <p>Bars supplement the supplied counts; missing weeks are not estimated.</p>
      </header>
      {points.length ? (
        <>
          <ol aria-label={`${playerName} weekly role evidence`}>
            {points.map((point) => (
              <li
                key={`${point.week}-${point.roleFamily}-${point.evidenceTeam?.id}`}
                className={!point.evidence ? "timeline-missing" : ""}
              >
                <span className="timeline-week">W{point.week}</span>
                <span className="timeline-bar" aria-hidden="true">
                  <span style={{ height: point.evidence ? `${Math.max(point.evidence.share * 100, 7)}%` : "0%" }} />
                </span>
                {point.evidence ? (
                  <>
                    <strong>{(point.evidence.share * 100).toFixed(1)}%</strong>
                    <span>{point.evidence.numerator}/{point.evidence.denominator}</span>
                  </>
                ) : (
                  <>
                    <strong>Missing</strong>
                    <span>Unavailable</span>
                  </>
                )}
                {point.partialGame ? <em>Reviewed partial</em> : null}
              </li>
            ))}
          </ol>
          <table>
            <caption className="sr-only">Exact weekly evidence for {playerName}</caption>
            <thead><tr><th>Week</th><th>Share</th><th>Raw evidence</th><th>Quality</th></tr></thead>
            <tbody>
              {points.map((point) => (
                <tr key={`${point.week}-${point.roleFamily}-${point.evidenceTeam?.id}`}>
                  <th scope="row">
                    {point.periodLabel} · {point.evidenceTeam?.id} ·{" "}
                    {point.roleLabel}
                  </th>
                  <td>{point.evidence ? `${(point.evidence.share * 100).toFixed(1)}%` : "Unavailable"}</td>
                  <td>{point.evidence ? `${point.evidence.numerator} of ${point.evidence.denominator} ${point.opportunityLabel}` : "No supplied evidence"}</td>
                  <td>
                    {point.participationQuality.replaceAll("_", " ")} · context{" "}
                    {point.supportingContextStatus}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="identity-inline-empty">No weekly chronology was supplied for this identity.</p>
      )}
    </section>
  );
}
