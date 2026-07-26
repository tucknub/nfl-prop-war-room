import Link from "next/link";
import { ArrowRightIcon, StatusIcon } from "@/components/icons";
import type {
  NoPublishedWeekHomepageFixture,
  UnavailableHomepageFixture,
} from "@/lib/types";

export function HomeState({
  data,
}: {
  data: NoPublishedWeekHomepageFixture | UnavailableHomepageFixture;
}) {
  const unavailable = data.status === "unavailable";

  return (
    <section
      className={`dashboard-panel home-state home-state-${unavailable ? "unavailable" : "empty"}`}
      aria-labelledby="home-state-title"
    >
      <div className="panel-heading">
        <span className={`panel-icon ${unavailable ? "panel-icon-decline" : "panel-icon-amber"}`} aria-hidden="true">
          <StatusIcon />
        </span>
        <span className="panel-label">
          {unavailable ? "Data unavailable" : "Publication status"}
        </span>
      </div>
      <div className="state-body">
        <span className="state-status">
          {unavailable ? "Data unavailable" : "Awaiting a completed week"}
        </span>
        <h1 id="home-state-title">{data.stateTitle}</h1>
        <p>
          {unavailable
            ? data.stateMessage
            : "No completed week has passed every publication check. DepthSnap will update after a completed week is verified."}
        </p>
        <div className="state-actions">
          <Link href="/data-status">
            View data status
            <ArrowRightIcon />
          </Link>
          <Link href="/methodology">How publishing works</Link>
        </div>
        <p className="state-safety">
          DepthSnap never substitutes estimated shares when verified data is absent.
        </p>
      </div>
    </section>
  );
}
