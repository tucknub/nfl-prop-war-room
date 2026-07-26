import { notFound } from "next/navigation";
import { ContractFailure } from "@/components/contract-failure";
import { PlayerDossier } from "@/components/player-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { loadPlayerData, loadReportData } from "@/lib/data-loader";
import { movementComparisonMap } from "@/lib/consumer-presentation";
import type { PlayerEvidenceBundle } from "@/lib/identity-types";
import type { PublishedMovementReportFixture } from "@/lib/report-types";

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ playerId: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ playerId }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="player dossier" />;
  const [result, movementResult] = await Promise.all([
    loadPlayerData(playerId, query.state),
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
    <PlayerDossier
      bundle={result.data as unknown as PlayerEvidenceBundle}
      comparisonByRecord={movementComparisonMap(
        movementResult.ok
          ? (movementResult.data as unknown as PublishedMovementReportFixture)
          : undefined,
      )}
    />
  );
}
