import { HomeState } from "@/components/home-state";
import { ReportLeaderboard } from "@/components/report-leaderboard";
import { LeadFinding, RoleChangeFeed } from "@/components/role-ui";
import { TeamSnapshot } from "@/components/team-snapshot";
import { getHomeFixture } from "@/data/home.fixture";
import {
  reportLeaderboardFixture,
  teamSnapshotFixture,
} from "@/data/home.presentation.fixture";

type HomePageProps = {
  searchParams: Promise<{ state?: string }>;
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const { state } = await searchParams;
  const data = getHomeFixture(state);

  return (
    <div className="page-shell">
      <div className="fixture-notice" role="note">
        <span aria-hidden="true" />
        {data.fixtureNotice}
      </div>

      {data.status === "published" ? (
        <div className="dashboard-grid">
          <LeadFinding finding={data.leadFinding} week={data.throughWeek} />
          <RoleChangeFeed findings={data.findings} />
          <TeamSnapshot data={teamSnapshotFixture} />
          <ReportLeaderboard data={reportLeaderboardFixture} />
        </div>
      ) : (
        <div className="state-grid">
          <HomeState data={data} />
        </div>
      )}

      <footer className="page-footer">
        <span>DepthSnap presents documented role evidence, not forecasts.</span>
        <div>
          <a href="/methodology">Methodology</a>
          <a href="/data-status">Data status</a>
        </div>
      </footer>
    </div>
  );
}
