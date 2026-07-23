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
        <>
          <LeadFinding finding={data.leadFinding} />
          <RoleChangeFeed findings={data.findings} />
          <ReportLinks reports={data.reportLinks} />
        </>
      ) : (
        <HomeState data={data} />
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
