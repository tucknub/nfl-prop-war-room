import { FixtureNotice } from "@/components/fixture-notice";
import { ReportsOverview } from "@/components/reports-overview";
import { backfieldReportFixture } from "@/data/reports.fixture";

export default function ReportsPage() {
  return (
    <div className="page-shell reports-overview-page">
      <FixtureNotice>{backfieldReportFixture.fixtureNotice}</FixtureNotice>
      <header className="reports-overview-header">
        <span role="heading" aria-level={2}>
          Reports
        </span>
        <h1>Follow the evidence</h1>
        <p>
          Every share includes its player count and matching team total. Open a
          report to inspect the supplied authority order and exact evidence.
        </p>
        <div>
          <strong>2025 · Week 18</strong>
          <small>Synthetic design fixture</small>
        </div>
      </header>
      <ReportsOverview />
    </div>
  );
}
