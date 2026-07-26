import { ContractFailure } from "@/components/contract-failure";
import { IdentityLoading, IdentityPageHeader, IdentityState } from "@/components/identity-primitives";
import { SearchExperience } from "@/components/search-experience";
import { loadSearchData } from "@/lib/data-loader";
import type { IdentitySearchParams, SearchIdentity } from "@/lib/identity-types";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<IdentitySearchParams>;
}) {
  const params = await searchParams;
  if (params.state === "loading") return <IdentityLoading title="identity search" />;
  const result = await loadSearchData(params.state);
  if (!result.ok) {
    return (
      <div className="page-shell identity-page-shell search-page-shell">
        <ContractFailure failure={result.failure} />
      </div>
    );
  }
  const data = result.data;
  return (
    <div className="page-shell identity-page-shell search-page-shell">
      <IdentityPageHeader
        eyebrow="Search"
        title="Find exact evidence"
        description={
          data.dataMode === "fixture"
            ? "Search only the synthetic team and player identity index, then open the supplied record directly."
            : "Search the validated team and player identity index, then open the supplied evidence record directly."
        }
        dataNotice={data.dataNotice}
        dataMode={data.dataMode}
        meta={`${data.records.length} ${data.dataMode} identities`}
      />
      {data.status === "published" ? (
        <SearchExperience
          index={data.records as unknown as readonly SearchIdentity[]}
          initialQuery={params.q ?? ""}
          shouldFocus={params.focus === "1"}
        />
      ) : (
        <IdentityState status={data.status} subject="identity search" />
      )}
    </div>
  );
}
