import { notFound } from "next/navigation";
import { PlayerDossier } from "@/components/player-dossier";
import { IdentityLoading } from "@/components/identity-primitives";
import { getPlayerBundle } from "@/data/identity-data";

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ playerId: string }>;
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ playerId }, query] = await Promise.all([params, searchParams]);
  if (query.state === "loading") return <IdentityLoading title="player dossier" />;
  const bundle = getPlayerBundle(playerId, query.state);
  if (!bundle) notFound();
  return <PlayerDossier bundle={bundle} />;
}
