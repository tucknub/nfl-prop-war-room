import { ReportPage } from "@/components/report-page";
import type { ReportSearchParams } from "@/lib/report-types";

export default function MovementPage({
  searchParams,
}: {
  searchParams: Promise<ReportSearchParams>;
}) {
  return <ReportPage family="role_movement" searchParams={searchParams} />;
}
