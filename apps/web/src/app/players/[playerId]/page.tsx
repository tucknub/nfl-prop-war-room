import { notFound } from "next/navigation";
import { ContractFailure } from "@/components/contract-failure";
import { PlayerDossier } from "@/components/player-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { loadPlayerData } from "@/lib/data-loader";
import type { PlayerEvidenceBundle } from "@/lib/identity-types";

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ playerId: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ playerId }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="player dossier" />;
  const result = await loadPlayerData(playerId, query.state);
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
    />
  );
}
