import Link from "next/link";
import { ArrowRightIcon, StatusIcon } from "@/components/icons";
import type {
  NoPublishedWeekReportFixture,
  UnavailableReportFixture,
} from "@/lib/report-types";

export function ReportState({
  data,
}: {
  data: NoPublishedWeekReportFixture | UnavailableReportFixture;
}) {
  const unavailable = data.status === "unavailable";

  return (
    <section
      className={`report-state report-state-${unavailable ? "unavailable" : "empty"}`}
      aria-labelledby="report-state-title"
    >
      <StatusIcon />
      <div>
        <span>{unavailable ? "Bundle unavailable" : "Publication status"}</span>
        <h2 id="report-state-title">{data.stateTitle}</h2>
        <p>{data.stateMessage}</p>
        <div className="report-state-actions">
          <Link href="/data-status">
            View data status
            <ArrowRightIcon />
          </Link>
          <Link href="/methodology">How publishing works</Link>
        </div>
      </div>
    </section>
  );
}
