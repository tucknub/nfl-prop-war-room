import { notFound } from "next/navigation";
import { ContractFailure } from "@/components/contract-failure";
import { TeamDossier } from "@/components/team-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { loadReportData, loadTeamData } from "@/lib/data-loader";
import { movementComparisonMap } from "@/lib/consumer-presentation";
import type { TeamEvidenceBundle } from "@/lib/identity-types";
import type { PublishedMovementReportFixture } from "@/lib/report-types";

export default async function TeamPage({
  params,
  searchParams,
}: {
  params: Promise<{ team: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ team }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="team dossier" />;
  const [result, movementResult] = await Promise.all([
    loadTeamData(team, query.state),
    loadReportData("role_movement", query.state),
  ]);
  if (!result.ok) {
    return (
      <div className="page-shell identity-page-shell">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  if (!result.data) notFound();
  return (
    <TeamDossier
      bundle={result.data as unknown as TeamEvidenceBundle}
      comparisonByRecord={movementComparisonMap(
        movementResult.ok
          ? (movementResult.data as unknown as PublishedMovementReportFixture)
          : undefined,
      )}
    />
  );
}
