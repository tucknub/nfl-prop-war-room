import { ContractFailure } from "@/components/contract-failure";
import { IdentityLoading, IdentityPageHeader, IdentityState } from "@/components/identity-primitives";
import { TeamDirectory } from "@/components/team-directory";
import { loadTeamsIndexData } from "@/lib/data-loader";
import type { IdentitySearchParams, TeamDirectoryRecord } from "@/lib/identity-types";

export default async function TeamsPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="team directory" />;
  const result = await loadTeamsIndexData(params.state);
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
      <h2 className="sr-only">Teams</h2>
      <IdentityPageHeader
        eyebrow="Teams"
        title="Team role structure"
        description="Locate a supplied team, scan its role leaders, and open one coherent evidence dossier."
        fixtureNotice={data.fixtureNotice}
        dataMode={data.dataMode}
        meta={`${data.season}${data.throughWeek ? ` · through Week ${data.throughWeek}` : ""}`}
      />
      {data.status !== "published" ? (
        <IdentityState status={data.status} subject="the team directory" />
      ) : (
        <TeamDirectory
          records={data.teams as unknown as readonly TeamDirectoryRecord[]}
          initialQuery={params.q ?? ""}
        />
      )}
    </div>
  );
}
