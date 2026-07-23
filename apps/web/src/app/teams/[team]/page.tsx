import { notFound } from "next/navigation";
import { ContractFailure } from "@/components/contract-failure";
import { TeamDossier } from "@/components/team-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { loadTeamData } from "@/lib/data-loader";
import type { TeamEvidenceBundle } from "@/lib/identity-types";

export default async function TeamPage({
  params,
  searchParams,
}: {
  params: Promise<{ team: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ team }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="team dossier" />;
  const result = await loadTeamData(team, query.state);
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
    />
  );
}
