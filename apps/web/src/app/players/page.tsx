import { IdentityLoading, IdentityPageHeader, IdentityState } from "@/components/identity-primitives";
import { PlayerDirectory } from "@/components/player-directory";
import { identityFixtureMetadata, teams } from "@/data/identity.fixture";
import { playerDirectoryRecords } from "@/data/identity-data";
import type { IdentitySearchParams } from "@/lib/identity-types";

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="player directory" />;
  const unavailable = params.state === "unavailable";
  const unpublished = params.state === "unpublished";
  return (
    <div className="page-shell identity-page-shell directory-page">
      <IdentityPageHeader
        eyebrow="Players"
        title="Player role evidence"
        description="Find a player and read the latest supplied share, raw counts, report memberships, and movement context."
        fixtureNotice={identityFixtureMetadata.fixtureNotice}
        meta={`${identityFixtureMetadata.season} · through Week ${identityFixtureMetadata.throughWeek}`}
      />
      {unavailable || unpublished ? (
        <IdentityState status={unavailable ? "unavailable" : "no_published_week"} subject="the player directory" />
      ) : (
        <PlayerDirectory
          records={playerDirectoryRecords}
          teams={teams.map((team) => team.id)}
          initialQuery={params.q ?? ""}
          initialTeam={params.team ?? "ALL"}
          initialPosition={params.position ?? "ALL"}
          initialReport={params.report ?? "ALL"}
        />
      )}
    </div>
  );
}
