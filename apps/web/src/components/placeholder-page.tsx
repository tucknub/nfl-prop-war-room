import Link from "next/link";
import { ArrowRightIcon } from "@/components/icons";

export function PlaceholderPage({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="page-shell placeholder-page">
      <span className="section-kicker">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
      <div className="placeholder-rule" />
      <p className="placeholder-note">
        This route is intentionally held for a later DepthSnap phase.
      </p>
      <Link className="back-link" href="/">
        Return to the feed
        <ArrowRightIcon />
      </Link>
    </div>
  );
}
