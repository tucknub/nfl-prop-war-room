import { LeadFinding, MovementFeed, Rankings, TeamCard } from "@/components/role-ui";
import { homeFixture } from "@/data/home.fixture";

export default function HomePage() {
  const data = homeFixture;

  return (
    <div className="page-shell">
      <section className="page-intro">
        <div>
          <span className="eyebrow">NFL role intelligence</span>
          <h1>DepthSnap Feed</h1>
          <p>See who gained control, who lost opportunity, and the raw evidence behind every change.</p>
        </div>
        <div className="status-stack">
          {data.fixture ? <span className="fixture-badge">Design fixture</span> : null}
          <span>{data.season} season · through Week {data.throughWeek}</span>
          <small>Validated data status: {data.status.replaceAll("_", " ").toLowerCase()}</small>
        </div>
      </section>

      <div className="top-grid">
        <LeadFinding finding={data.lead} />
        <MovementFeed findings={data.movement} />
      </div>

      <div className="lower-grid">
        <TeamCard snapshot={data.teamSnapshot} />
        <Rankings findings={data.rankings} />
      </div>

      <footer className="page-footer">
        <span>DepthSnap shows documented role evidence, not forecasts or recommendations.</span>
        <a href="/data-status">View data status</a>
      </footer>
    </div>
  );
}
