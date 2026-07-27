import type { SuppliedMovementRecord } from "@/lib/identity-types";
import type {
  MovementEvidenceRow,
  PublishedMovementReportFixture,
  ReportPeriod,
} from "@/lib/report-types";
import type { MovementEvidence, RawShareEvidence } from "@/lib/types";

export const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

export const formatPoints = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

export const possessiveName = (value: string) =>
  value.endsWith("s") ? `${value}’` : `${value}’s`;

export function movementDirection(
  value: number,
): "gain" | "decline" | "stable" {
  if (value > 0) return "gain";
  if (value < 0) return "decline";
  return "stable";
}

export function movementLabel(value: number) {
  const direction = movementDirection(value);
  if (direction === "gain") return "Gain";
  if (direction === "decline") return "Decline";
  return "Stable";
}

export function movementVerb(value: number) {
  const direction = movementDirection(value);
  if (direction === "gain") return "rose";
  if (direction === "decline") return "fell";
  return "held steady";
}

export function movementHeadline(
  playerName: string,
  roleLabel: string,
  movement: MovementEvidence,
) {
  return `${possessiveName(playerName)} ${roleLabel} ${movementVerb(
    movement.percentagePointChange,
  )} from ${formatPercent(movement.previous.share)} to ${formatPercent(
    movement.current.share,
  )}.`;
}

export function periodLabel(period: ReportPeriod) {
  return period.startWeek === period.endWeek
    ? `Week ${period.startWeek}`
    : `Weeks ${period.startWeek}–${period.endWeek}`;
}

export function comparisonLabel(
  currentPeriod: ReportPeriod,
  priorPeriod?: ReportPeriod,
) {
  const current = periodLabel(currentPeriod);
  return priorPeriod
    ? `${current} compared with ${periodLabel(priorPeriod)}`
    : current;
}

export function rollingFourWeekComparison(throughWeek: number) {
  const currentStart = Math.max(1, throughWeek - 3);
  const priorEnd = Math.max(1, currentStart - 1);
  const priorStart = Math.max(1, priorEnd - 3);
  return `Weeks ${currentStart}–${throughWeek} compared with Weeks ${priorStart}–${priorEnd}`;
}

export function normalGameComparison(
  current: RawShareEvidence,
  normal?: RawShareEvidence,
) {
  if (!normal) {
    return "Normal-game context is unavailable for this record.";
  }

  const normalPercent = formatPercent(normal.share);
  const currentPercent = formatPercent(current.share);
  const difference = (normal.share - current.share) * 100;

  if (Math.abs(difference) < 2) {
    return `The normal-game share was nearly unchanged: ${normalPercent} compared with ${currentPercent} overall.`;
  }
  if (difference < 0) {
    return `The share was lower when unusual game situations were excluded: ${normalPercent} compared with ${currentPercent} overall.`;
  }
  return `The share was higher when unusual game situations were excluded: ${normalPercent} compared with ${currentPercent} overall.`;
}

export function metricLabel(label: RawShareEvidence["opportunityLabel"]) {
  if (label === "opportunities") return "Total opportunities";
  if (label === "carries") return "Carries";
  return "Targets";
}

function evidenceKey(evidence: RawShareEvidence) {
  return [
    evidence.opportunityLabel,
    evidence.numerator,
    evidence.denominator,
    evidence.share.toFixed(12),
  ].join(":");
}

export function movementRecordKey(
  record: Pick<
    SuppliedMovementRecord | MovementEvidenceRow,
    "player" | "evidenceTeam" | "roleFamily" | "movement"
  >,
) {
  return [
    record.player.id,
    record.evidenceTeam.id,
    record.roleFamily,
    evidenceKey(record.movement.previous),
    evidenceKey(record.movement.current),
    record.movement.percentagePointChange.toFixed(9),
  ].join("|");
}

export function movementComparisonMap(
  report: PublishedMovementReportFixture | null | undefined,
) {
  const labels: Record<string, string> = {};
  if (!report || report.status !== "published") return labels;

  for (const view of report.views) {
    const option = report.availableViews.find(
      (candidate) => candidate.id === view.viewId,
    );
    if (!option) continue;
    const label = comparisonLabel(option.currentPeriod, option.priorPeriod);
    for (const row of view.rows) {
      labels[movementRecordKey(row)] ??= label;
    }
  }
  return labels;
}
