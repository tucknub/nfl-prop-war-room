import { ReportPage } from "@/components/report-page";
import type { ReportSearchParams } from "@/lib/report-types";

export default function BackfieldPage({
  searchParams,
}: {
  searchParams: Promise<ReportSearchParams>;
}) {
  return (
    <ReportPage family="backfield_control" searchParams={searchParams} />
  );
}
