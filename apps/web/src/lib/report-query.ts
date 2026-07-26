import type {
  ParsedReportQuery,
  ReportMetadata,
  ReportSearchParams,
  ReportSort,
} from "@/lib/report-types";

const positions = new Set(["ALL", "RB", "WR", "TE"]);
const presentationSorts = new Set<ReportSort>([
  "authority",
  "share",
  "share_asc",
  "gainers",
  "decliners",
  "absolute_change",
]);
const directions = new Set(["gains", "declines", "all"]);

export function parseReportQuery(
  metadata: ReportMetadata,
  searchParams: ReportSearchParams,
): ParsedReportQuery {
  const view = metadata.availableViews.some(
    (option) => option.id === searchParams.view,
  )
    ? searchParams.view!
    : metadata.defaultView;
  const requestedSort = searchParams.sort as ReportSort | undefined;
  const defaultSort =
    metadata.reportFamily === "role_movement" ? "gainers" : "share";
  const sort =
    requestedSort && presentationSorts.has(requestedSort)
      ? requestedSort
      : defaultSort;
  const requestedTeam = searchParams.team?.toUpperCase();
  const team =
    requestedTeam && metadata.teamOptions.includes(requestedTeam)
      ? requestedTeam
      : "ALL";
  const requestedPosition = searchParams.position?.toUpperCase();
  const defaultPosition =
    metadata.reportFamily === "target_hierarchy" ? "WR" : "ALL";
  const position =
    requestedPosition && positions.has(requestedPosition)
      ? (requestedPosition as ParsedReportQuery["position"])
      : defaultPosition;
  const metric =
    searchParams.metric === "carries" ? "carries" : "opportunities";
  const direction =
    searchParams.direction && directions.has(searchParams.direction)
      ? (searchParams.direction as ParsedReportQuery["direction"])
      : "gains";
  const requestedPage = Number.parseInt(searchParams.page ?? "1", 10);
  const page =
    Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;

  return { view, sort, team, position, metric, direction, page };
}
