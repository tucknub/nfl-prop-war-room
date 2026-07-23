import { IdentityLoading, IdentityPageHeader, IdentityState } from "@/components/identity-primitives";
import { TeamDirectory } from "@/components/team-directory";
import { identityFixtureMetadata } from "@/data/identity.fixture";
import { teamDirectoryRecords } from "@/data/identity-data";
import type { IdentitySearchParams } from "@/lib/identity-types";

export default async function TeamsPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="team directory" />;
  const unavailable = params.state === "unavailable";
  const unpublished = params.state === "unpublished";
  return (
    <div className="page-shell identity-page-shell directory-page">
      <h2 className="sr-only">Teams</h2>
      <IdentityPageHeader
        eyebrow="Teams"
        title="Team role structure"
        description="Locate a fixture team, scan its supplied role leaders, and open one coherent evidence dossier."
        fixtureNotice={identityFixtureMetadata.fixtureNotice}
        meta={`${identityFixtureMetadata.season} · through Week ${identityFixtureMetadata.throughWeek}`}
      />
      {unavailable || unpublished ? (
        <IdentityState status={unavailable ? "unavailable" : "no_published_week"} subject="the team directory" />
      ) : (
        <TeamDirectory records={teamDirectoryRecords} initialQuery={params.q ?? ""} />
      )}
    </div>
  );
}
