import { ContractFailure } from "@/components/contract-failure";
import { FixtureNotice } from "@/components/fixture-notice";
import { ReportExperience } from "@/components/report-experience";
import { ReportLoading } from "@/components/report-loading";
import { ReportState } from "@/components/report-state";
import { loadReportData } from "@/lib/data-loader";
import { parseReportQuery } from "@/lib/report-query";
import type { ReportFixture, ReportSearchParams } from "@/lib/report-types";
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

  const result = await loadReportData(family, params.state);
  if (!result.ok) {
    return (
      <div className="page-shell report-page-shell">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const data = result.data as unknown as ReportFixture;

  return (
    <div className="page-shell report-page-shell">
      {data.dataMode === "fixture" ? (
        <FixtureNotice>{data.dataNotice}</FixtureNotice>
      ) : null}
      {data.status === "published" ? (
        <ReportExperience
          data={data}
          initialQuery={parseReportQuery(data, params)}
        />
      ) : (
        <div className="report-page">
          <header className="report-header">
            <div className="report-title-block">
              <span>
                Report · {data.season}
                {data.throughWeek ? ` Week ${data.throughWeek}` : ""}
              </span>
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
