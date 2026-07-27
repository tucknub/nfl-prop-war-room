"use client";

import { useMemo, useState } from "react";
import {
  formatPercent,
  metricLabel,
} from "@/lib/consumer-presentation";
import type { WeeklyEvidencePoint } from "@/lib/identity-types";
import type { RawShareEvidence } from "@/lib/types";

type Metric = RawShareEvidence["opportunityLabel"];

const chart = {
  width: 900,
  height: 264,
  left: 48,
  right: 20,
  top: 18,
  bottom: 40,
} as const;

function isCaution(point: WeeklyEvidencePoint | undefined) {
  return Boolean(
    point &&
      (point.participationQuality !== "complete" ||
        point.supportingContextStatus === "unavailable"),
  );
}

function qualityLabel(point: WeeklyEvidencePoint | undefined) {
  if (!point?.evidence) return "No evidence";
  if (!isCaution(point)) return "Normal";
  if (point.participationQuality !== "complete") {
    return "Partial participation";
  }
  return "Context unavailable";
}

function technicalQuality(point: WeeklyEvidencePoint | undefined) {
  if (!point?.evidence) return "No evidence";
  return `Participation: ${point.participationQuality}; context: ${point.supportingContextStatus}`;
}

function pointX(index: number, count: number) {
  const plotWidth = chart.width - chart.left - chart.right;
  return chart.left + (index * plotWidth) / Math.max(count - 1, 1);
}

function pointY(share: number) {
  const plotHeight = chart.height - chart.top - chart.bottom;
  return chart.top + (1 - Math.min(Math.max(share, 0), 1)) * plotHeight;
}

function lineSegments(points: readonly (WeeklyEvidencePoint | undefined)[]) {
  const segments: string[][] = [];
  let current: string[] = [];
  points.forEach((point, index) => {
    if (!point?.evidence) {
      if (current.length) segments.push(current);
      current = [];
      return;
    }
    current.push(`${pointX(index, points.length)},${pointY(point.evidence.share)}`);
  });
  if (current.length) segments.push(current);
  return segments;
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
  const selectedPoint = pointsByWeekAndMetric.get(
    `${selectedWeek}:${metric}`,
  );
  const segments = lineSegments(visiblePoints);

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

          <p className="weekly-chart-hint">
            Full season chart. On smaller screens, scroll horizontally to review
            every week.
          </p>
          <div
            className="weekly-chart-scroll"
            role="region"
            aria-label={`${playerName} ${metricLabel(metric).toLowerCase()} full season trend`}
            tabIndex={0}
          >
            <div
              className="weekly-trend-chart"
              style={{ width: chart.width, height: chart.height }}
            >
              <svg
                viewBox={`0 0 ${chart.width} ${chart.height}`}
                aria-hidden="true"
              >
                {[0, 25, 50, 75, 100].map((percent) => {
                  const y = pointY(percent / 100);
                  return (
                    <g key={percent}>
                      <line
                        className="weekly-grid-line"
                        x1={chart.left}
                        x2={chart.width - chart.right}
                        y1={y}
                        y2={y}
                      />
                      <text x={chart.left - 9} y={y + 4} textAnchor="end">
                        {percent}%
                      </text>
                    </g>
                  );
                })}
                {segments.map((segment, index) => (
                  <polyline
                    className="weekly-trend-line"
                    key={index}
                    points={segment.join(" ")}
                  />
                ))}
                {weeks.map((week, index) => (
                  <text
                    className="weekly-axis-label"
                    key={week}
                    x={pointX(index, weeks.length)}
                    y={chart.height - 14}
                    textAnchor="middle"
                  >
                    W{week}
                  </text>
                ))}
              </svg>
              {weeks.map((week, index) => {
                const point = visiblePoints[index];
                const selected = selectedWeek === week;
                const y = point?.evidence
                  ? pointY(point.evidence.share)
                  : chart.height - chart.bottom;
                return (
                  <button
                    type="button"
                    className={`weekly-chart-point${point?.evidence ? "" : " weekly-chart-point-missing"}${isCaution(point) ? " weekly-chart-point-caution" : ""}`}
                    key={week}
                    style={{
                      left: pointX(index, weeks.length),
                      top: y,
                    }}
                    aria-pressed={selected}
                    aria-label={
                      point?.evidence
                        ? `Week ${week}, ${formatPercent(point.evidence.share)}, ${point.evidence.numerator} of ${point.evidence.denominator} ${point.evidence.opportunityLabel}, ${qualityLabel(point)}`
                        : `Week ${week}, no evidence`
                    }
                    onClick={() => setSelectedWeek(week)}
                    onFocus={() => setSelectedWeek(week)}
                  >
                    <span aria-hidden="true" />
                    {!point?.evidence ? (
                      <em aria-hidden="true">No evidence</em>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

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
                <small
                  className={isCaution(selectedPoint) ? "quality-caution" : ""}
                  title={technicalQuality(selectedPoint)}
                >
                  {qualityLabel(selectedPoint)}
                </small>
              </>
            ) : (
              <>
                <strong>No evidence</strong>
                <p>No role evidence is available for this metric and week.</p>
              </>
            )}
          </div>

          <ul className="weekly-text-equivalent sr-only">
            {weeks.map((week, index) => {
              const point = visiblePoints[index];
              return (
                <li key={week}>
                  <strong>Week {week}:</strong>{" "}
                  {point?.evidence
                    ? `${formatPercent(point.evidence.share)} · ${point.evidence.numerator} of ${point.evidence.denominator} ${point.evidence.opportunityLabel} · ${qualityLabel(point)} · ${technicalQuality(point)}`
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
                    <th>Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {weeks.map((week) => {
                    const weekPoints = metrics.map((option) =>
                      pointsByWeekAndMetric.get(`${week}:${option}`),
                    );
                    const qualityPoint = weekPoints.find(
                      (point) => point?.evidence,
                    );
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
                        <td
                          className={
                            isCaution(qualityPoint) ? "quality-caution" : ""
                          }
                          title={technicalQuality(qualityPoint)}
                        >
                          {qualityLabel(qualityPoint)}
                        </td>
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
