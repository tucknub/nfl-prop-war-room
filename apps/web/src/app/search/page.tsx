import { IdentityLoading, IdentityPageHeader } from "@/components/identity-primitives";
import { SearchExperience } from "@/components/search-experience";
import { identityFixtureMetadata } from "@/data/identity.fixture";
import { searchIndex } from "@/data/identity-data";
import type { IdentitySearchParams } from "@/lib/identity-types";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="identity search" />;
  return (
    <div className="page-shell identity-page-shell search-page-shell">
      <IdentityPageHeader
        eyebrow="Search"
        title="Find exact evidence"
        description="Search only the synthetic team and player identity index, then open the supplied record directly."
        fixtureNotice={identityFixtureMetadata.fixtureNotice}
        meta={`${searchIndex.length} fixture identities`}
      />
      <SearchExperience index={searchIndex} initialQuery={params.q ?? ""} shouldFocus={params.focus === "1"} />
    </div>
  );
}
