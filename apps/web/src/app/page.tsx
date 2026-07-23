import { HomeState } from "@/components/home-state";
import {
  LeadFinding,
  ReportLinks,
  RoleChangeFeed,
} from "@/components/role-ui";
import { getHomeFixture } from "@/data/home.fixture";

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
          <LeadFinding finding={data.leadFinding} />
          <RoleChangeFeed findings={data.findings} />
          <ReportLinks reports={data.reportLinks} />
        </div>
      ) : (
        <div className="state-grid">
          <HomeState data={data} />
          <ReportLinks reports={data.reportLinks} />
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
