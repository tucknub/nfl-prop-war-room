import { ContractFailure } from "@/components/contract-failure";
import { FixtureNotice } from "@/components/fixture-notice";
import { HomeState } from "@/components/home-state";
import { ReportLeaderboard } from "@/components/report-leaderboard";
import { LeadFinding, RoleChangeFeed } from "@/components/role-ui";
import { TeamSnapshot } from "@/components/team-snapshot";
import { loadHomeData } from "@/lib/data-loader";
import type { HomepageFixture } from "@/lib/types";

type HomepageStateFixture = Exclude<
  HomepageFixture,
  { status: "published" }
>;

type HomePageProps = {
  searchParams: Promise<{ state?: string }>;
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const { state } = await searchParams;
  const result = await loadHomeData(state);
  if (!result.ok) {
    return (
      <div className="page-shell">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const data = result.data;

  return (
    <div className="page-shell">
      {data.dataMode === "fixture" ? (
        <FixtureNotice>{data.dataNotice}</FixtureNotice>
      ) : null}

      {data.status === "published" ? (
        <div className="dashboard-grid">
          <LeadFinding finding={data.leadFinding} week={data.throughWeek} />
          <RoleChangeFeed findings={data.findings} />
          <TeamSnapshot data={data.teamSnapshot} throughWeek={data.throughWeek} />
          <ReportLeaderboard data={data.reportLeaderboard} />
        </div>
      ) : (
        <div className="state-grid">
          <HomeState data={data as unknown as HomepageStateFixture} />
        </div>
      )}

      <footer className="page-footer">
        <span>DepthSnap presents role evidence, not forecasts.</span>
        <div>
          <a href="/methodology">Methodology</a>
          <a href="/data-status">Data status</a>
        </div>
      </footer>
    </div>
  );
}
