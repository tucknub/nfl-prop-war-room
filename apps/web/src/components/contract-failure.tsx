import Link from "next/link";
import type { LoaderFailure } from "@/lib/data-contract";

export function ContractFailure({
  failure,
  compact = false,
}: {
  failure: LoaderFailure;
  compact?: boolean;
}) {
  return (
    <section
      className={`contract-failure${compact ? " contract-failure-compact" : ""}`}
      aria-labelledby="contract-failure-title"
      data-testid="contract-failure"
    >
      <span className="contract-failure-code">{failure.category}</span>
      <h1 id="contract-failure-title">{failure.title}</h1>
      <p>{failure.publicDetail}</p>
      <div className="contract-failure-actions">
        <Link href="/data-status">Open Data Status</Link>
        <Link href="/methodology">Read Methodology</Link>
      </div>
    </section>
  );
}
