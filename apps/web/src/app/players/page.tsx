import { ContractFailure } from "@/components/contract-failure";
import { IdentityLoading, IdentityPageHeader, IdentityState } from "@/components/identity-primitives";
import { PlayerDirectory } from "@/components/player-directory";
import { loadPlayersIndexData } from "@/lib/data-loader";
import type { IdentitySearchParams, PlayerDirectoryRecord } from "@/lib/identity-types";

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="player directory" />;
  const result = await loadPlayersIndexData(params.state);
  if (!result.ok) {
    return (
      <div className="page-shell identity-page-shell directory-page">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const data = result.data;
  return (
    <div className="page-shell identity-page-shell directory-page">
      <IdentityPageHeader
        eyebrow="Players"
        title="Player role evidence"
        description="Find a player and read the latest role share, raw counts, current reports, and recent changes."
        dataNotice={data.dataNotice}
        dataMode={data.dataMode}
        meta={`${data.season}${data.throughWeek ? ` · through Week ${data.throughWeek}` : ""}`}
      />
      {data.status !== "published" ? (
        <IdentityState status={data.status} subject="the player directory" />
      ) : (
        <PlayerDirectory
          records={data.players as unknown as readonly PlayerDirectoryRecord[]}
          teams={data.teamOptions}
          initialQuery={params.q ?? ""}
          initialTeam={params.team ?? "ALL"}
          initialPosition={params.position ?? "ALL"}
          initialReport={params.report ?? "ALL"}
        />
      )}
    </div>
  );
}
