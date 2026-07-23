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
      className={`home-state home-state-${unavailable ? "unavailable" : "empty"}`}
      aria-labelledby="home-state-title"
    >
      <div className="state-glyph" aria-hidden="true">
        <StatusIcon />
      </div>
      <span className="section-kicker">
        {unavailable ? "Data unavailable" : "Awaiting a published week"}
      </span>
      <h1 id="home-state-title">{data.stateTitle}</h1>
      <p>{data.stateMessage}</p>
      <div className="state-actions">
        <Link href="/data-status">
          View data status
          <ArrowRightIcon />
        </Link>
        <Link href="/methodology">How publishing works</Link>
      </div>
      <p className="state-safety">
        DepthSnap never substitutes estimated shares when authoritative data is
        absent.
      </p>
    </section>
  );
}
