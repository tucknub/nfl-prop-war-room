import { ContractFailure } from "@/components/contract-failure";
import { FixtureNotice } from "@/components/fixture-notice";
import { IdentityState } from "@/components/identity-primitives";
import { ReportsOverview } from "@/components/reports-overview";
import { loadReportsIndexData } from "@/lib/data-loader";

export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const params = await searchParams;
  const result = await loadReportsIndexData(params.state);
  if (!result.ok) {
    return (
      <div className="page-shell reports-overview-page">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const data = result.data;
  return (
    <div className="page-shell reports-overview-page">
      {data.dataMode === "fixture" ? (
        <FixtureNotice>{data.dataNotice}</FixtureNotice>
      ) : null}
      <header className="reports-overview-header">
        <span role="heading" aria-level={2}>
          Reports
        </span>
        <h1>Three tools for understanding NFL roles</h1>
        <p>
          See who controls backfields, who earns targets, and whose role changed.
          Every percentage includes its player count and matching team total.
        </p>
        <div>
          <strong>
            {data.season}
            {data.throughWeek ? ` · Week ${data.throughWeek}` : ""}
          </strong>
          <small>
            {data.dataMode === "fixture"
              ? "Synthetic design fixture"
              : "Data verified"}
          </small>
        </div>
      </header>
      {data.status === "published" ? (
        <ReportsOverview data={data} />
      ) : (
        <IdentityState status={data.status} subject="the reports overview" />
      )}
    </div>
  );
}
