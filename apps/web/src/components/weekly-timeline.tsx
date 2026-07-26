"use client";

import { useMemo, useState } from "react";
import {
  formatPercent,
  metricLabel,
} from "@/lib/consumer-presentation";
import type { WeeklyEvidencePoint } from "@/lib/identity-types";
import type { RawShareEvidence } from "@/lib/types";

type Metric = RawShareEvidence["opportunityLabel"];

function qualityLabel(point: WeeklyEvidencePoint | undefined) {
  if (!point) return "No evidence";
  const participation = point.participationQuality.replaceAll("_", " ");
  const context =
    point.supportingContextStatus === "available"
      ? "context available"
      : "context unavailable";
  return `${participation} · ${context}`;
}

export function WeeklyTimeline({
  points,
  playerName,
  throughWeek,
  primaryRoleFamily,
}: {
  points: readonly WeeklyEvidencePoint[];
  playerName: string;
  throughWeek: number;
  primaryRoleFamily?: string;
}) {
  const metrics = useMemo(
    () => [...new Set(points.map((point) => point.opportunityLabel))],
    [points],
  );
  const preferredMetric =
    points.find((point) => point.roleFamily === primaryRoleFamily)
      ?.opportunityLabel ??
    (metrics.includes("opportunities") ? "opportunities" : metrics[0]) ??
    "opportunities";
  const [metric, setMetric] = useState<Metric>(preferredMetric);
  const [selectedWeek, setSelectedWeek] = useState(throughWeek);
  const weeks = useMemo(
    () => Array.from({ length: throughWeek }, (_, index) => index + 1),
    [throughWeek],
  );
  const pointsByWeekAndMetric = useMemo(() => {
    const map = new Map<string, WeeklyEvidencePoint>();
    for (const point of points) {
      map.set(`${point.week}:${point.opportunityLabel}`, point);
    }
    return map;
  }, [points]);
  const visiblePoints = weeks.map((week) =>
    pointsByWeekAndMetric.get(`${week}:${metric}`),
  );
  const selectedPoint =
    pointsByWeekAndMetric.get(`${selectedWeek}:${metric}`);

  return (
    <section
      className="dossier-section weekly-timeline"
      aria-labelledby="weekly-role-timeline"
    >
      <header>
        <div>
          <p className="identity-eyebrow">Weekly trend</p>
          <h2 id="weekly-role-timeline">How the role changed week by week</h2>
        </div>
        <p>Choose one metric. Missing weeks are labeled “No evidence.”</p>
      </header>

      {points.length ? (
        <>
          <fieldset className="consumer-segmented weekly-metric-control">
            <legend>Weekly metric</legend>
            <div>
              {metrics.map((option) => (
                <button
                  type="button"
                  key={option}
                  aria-pressed={metric === option}
                  onClick={() => setMetric(option)}
                >
                  {metricLabel(option)}
                </button>
              ))}
            </div>
          </fieldset>

          <ol
            className="weekly-trend-chart"
            aria-label={`${playerName} ${metricLabel(metric).toLowerCase()} by week`}
          >
            {weeks.map((week, index) => {
              const point = visiblePoints[index];
              const selected = selectedWeek === week;
              return (
                <li key={week} className={!point?.evidence ? "timeline-missing" : ""}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    aria-label={
                      point?.evidence
                        ? `Week ${week}, ${formatPercent(point.evidence.share)}, ${point.evidence.numerator} of ${point.evidence.denominator} ${point.evidence.opportunityLabel}`
                        : `Week ${week}, no evidence`
                    }
                    onClick={() => setSelectedWeek(week)}
                    onFocus={() => setSelectedWeek(week)}
                  >
                    <span className="timeline-week">W{week}</span>
                    <span className="timeline-bar" aria-hidden="true">
                      <span
                        style={{
                          height: point?.evidence
                            ? `${Math.max(point.evidence.share * 100, 5)}%`
                            : "0%",
                        }}
                      />
                    </span>
                    <strong>
                      {point?.evidence
                        ? formatPercent(point.evidence.share)
                        : "—"}
                    </strong>
                  </button>
                </li>
              );
            })}
          </ol>

          <div className="weekly-trend-detail" aria-live="polite">
            <span>Week {selectedWeek}</span>
            {selectedPoint?.evidence ? (
              <>
                <strong>{formatPercent(selectedPoint.evidence.share)}</strong>
                <p>
                  {selectedPoint.evidence.numerator} of{" "}
                  {selectedPoint.evidence.denominator}{" "}
                  {selectedPoint.evidence.opportunityLabel} ·{" "}
                  {selectedPoint.roleLabel}
                </p>
                <small>{qualityLabel(selectedPoint)}</small>
              </>
            ) : (
              <>
                <strong>No evidence</strong>
                <p>No role evidence is available for this metric and week.</p>
              </>
            )}
          </div>

          <ul className="weekly-text-equivalent">
            {weeks.map((week, index) => {
              const point = visiblePoints[index];
              return (
                <li key={week}>
                  <strong>Week {week}:</strong>{" "}
                  {point?.evidence
                    ? `${formatPercent(point.evidence.share)} · ${point.evidence.numerator} of ${point.evidence.denominator} ${point.evidence.opportunityLabel} · ${qualityLabel(point)}`
                    : "No evidence"}
                </li>
              );
            })}
          </ul>

          <details className="exact-weekly-evidence">
            <summary>View exact weekly counts</summary>
            <div className="weekly-evidence-table-wrap">
              <table>
                <caption className="sr-only">
                  Exact weekly counts for {playerName}
                </caption>
                <thead>
                  <tr>
                    <th>Week</th>
                    {metrics.map((option) => (
                      <th key={option}>{metricLabel(option)}</th>
                    ))}
                    <th>Context</th>
                  </tr>
                </thead>
                <tbody>
                  {weeks.map((week) => {
                    const weekPoints = metrics.map((option) =>
                      pointsByWeekAndMetric.get(`${week}:${option}`),
                    );
                    const qualityPoint = weekPoints.find(Boolean);
                    return (
                      <tr key={week}>
                        <th scope="row">Week {week}</th>
                        {weekPoints.map((point, index) => (
                          <td key={metrics[index]}>
                            {point?.evidence
                              ? `${formatPercent(point.evidence.share)} · ${point.evidence.numerator}/${point.evidence.denominator}`
                              : "No evidence"}
                          </td>
                        ))}
                        <td>{qualityLabel(qualityPoint)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p className="identity-inline-empty">
          No weekly evidence is available for this player.
        </p>
      )}
    </section>
  );
}
