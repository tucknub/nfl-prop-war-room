import { notFound } from "next/navigation";
import { TeamDossier } from "@/components/team-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { getTeamBundle } from "@/data/identity-data";

export default async function TeamPage({
  params,
  searchParams,
}: {
  params: Promise<{ team: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ team }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="team dossier" />;
  const bundle = getTeamBundle(team, query.state);
  if (!bundle) notFound();
  return <TeamDossier bundle={bundle} />;
}
