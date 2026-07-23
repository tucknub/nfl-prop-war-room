import type {
  ParsedReportQuery,
  ReportMetadata,
  ReportSearchParams,
  ReportSort,
} from "@/lib/report-types";

const positions = new Set(["ALL", "RB", "WR", "TE"]);

export function parseReportQuery(
  metadata: ReportMetadata,
  searchParams: ReportSearchParams,
): ParsedReportQuery {
  const view = metadata.availableViews.some(
    (option) => option.id === searchParams.view,
  )
    ? searchParams.view!
    : metadata.defaultView;
  const sort = metadata.availableSorts.some(
    (option) => option.id === searchParams.sort,
  )
    ? (searchParams.sort as ReportSort)
    : metadata.defaultSort;
  const requestedTeam = searchParams.team?.toUpperCase();
  const team =
    requestedTeam && metadata.teamOptions.includes(requestedTeam)
      ? requestedTeam
      : "ALL";
  const requestedPosition = searchParams.position?.toUpperCase();
  const position =
    requestedPosition && positions.has(requestedPosition)
      ? (requestedPosition as ParsedReportQuery["position"])
      : "ALL";
  const requestedPage = Number.parseInt(searchParams.page ?? "1", 10);
  const page =
    Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;

  return { view, sort, team, position, page };
}
