import { FixtureNotice } from "@/components/fixture-notice";
import { ReportExperience } from "@/components/report-experience";
import { ReportLoading } from "@/components/report-loading";
import { ReportState } from "@/components/report-state";
import { getReportFixture } from "@/data/reports.fixture";
import { parseReportQuery } from "@/lib/report-query";
import type { ReportSearchParams } from "@/lib/report-types";
import type { ReportFamily } from "@/lib/types";

export async function ReportPage({
  family,
  searchParams,
}: {
  family: ReportFamily;
  searchParams: Promise<ReportSearchParams>;
}) {
  const params = await searchParams;

  if (params.state === "loading") {
    return <ReportLoading />;
  }

  const data = getReportFixture(family, params.state);

  return (
    <div className="page-shell report-page-shell">
      <FixtureNotice>{data.fixtureNotice}</FixtureNotice>
      {data.status === "published" ? (
        <ReportExperience
          data={data}
          initialQuery={parseReportQuery(data, params)}
        />
      ) : (
        <div className="report-page">
          <header className="report-header">
            <div className="report-title-block">
              <span>Report · 2025 Week {data.throughWeek}</span>
              <h1>{data.title}</h1>
              <p>{data.question}</p>
            </div>
          </header>
          <ReportState data={data} />
        </div>
      )}
    </div>
  );
}
