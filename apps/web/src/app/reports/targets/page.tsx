import { ReportPage } from "@/components/report-page";
import type { ReportSearchParams } from "@/lib/report-types";

export default function TargetsPage({
  searchParams,
}: {
  searchParams: Promise<ReportSearchParams>;
}) {
  return <ReportPage family="target_hierarchy" searchParams={searchParams} />;
}
