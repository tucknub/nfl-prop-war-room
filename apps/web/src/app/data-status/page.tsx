import Link from "next/link";
import { ContractFailure } from "@/components/contract-failure";
import { CopyHashButton } from "@/components/copy-hash-button";
import { FixtureNotice } from "@/components/fixture-notice";
import { loadStatusData } from "@/lib/data-loader";

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export default async function DataStatusPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const params = await searchParams;
  const result = await loadStatusData(params.state);
  if (!result.ok) {
    return (
      <div className="page-shell data-status-page">
        <header className="status-hero">
          <div>
            <span className="section-kicker">Data Status</span>
            <h1>Contract validation stopped publication.</h1>
            <p>
              DepthSnap did not substitute fixture evidence or expose internal
              diagnostics.
            </p>
          </div>
          <div
            className="publication-seal publication-unavailable"
            aria-label="Publication state: unavailable"
          >
            <span aria-hidden="true" />
            <small>Publication state</small>
            <strong>Unavailable</strong>
            <em>Contract check failed closed</em>
          </div>
        </header>
        <ContractFailure failure={result.failure} compact />
      </div>
    );
  }
  const status = result.data;
  const manifest = result.manifest;
  const publicationLabel =
    status.status === "published"
      ? "Published"
      : status.status === "no_published_week"
        ? "No published week"
        : "Unavailable";

  return (
    <div className="page-shell data-status-page">
      {status.dataMode === "fixture" ? (
        <FixtureNotice>{status.dataNotice}</FixtureNotice>
      ) : null}
      <header className="status-hero">
        <div>
          <span className="section-kicker">Data Status</span>
          <h1>Publication integrity, in public.</h1>
          <p>
            Supplied freshness, bundle validation, and known limits—without
            local paths, private source details, or estimated replacements.
          </p>
        </div>
        <div
          className={`publication-seal publication-${status.status}`}
          aria-label={`Publication state: ${publicationLabel}`}
        >
          <span aria-hidden="true" />
          <small>Publication state</small>
          <strong>{publicationLabel}</strong>
          <em>
            {status.throughWeek
              ? `${status.season} · through Week ${status.throughWeek}`
              : `${status.season} · no week supplied`}
          </em>
        </div>
      </header>

      <section className="status-metadata" aria-labelledby="status-metadata-title">
        <div className="status-section-heading">
          <span>Bundle identity</span>
          <h2 id="status-metadata-title">What this application loaded</h2>
        </div>
        <dl>
          <div>
            <dt>Product</dt>
            <dd>{manifest.productId}</dd>
          </div>
          <div>
            <dt>Data mode</dt>
            <dd>{status.dataMode}</dd>
          </div>
          <div>
            <dt>Validation result</dt>
            <dd>{manifest.validationResult.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Publication result</dt>
            <dd>{manifest.publicationStatus.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Season</dt>
            <dd>{manifest.season}</dd>
          </div>
          <div>
            <dt>Published through</dt>
            <dd>
              {manifest.throughWeek
                ? `Week ${manifest.throughWeek}`
                : "No week supplied"}
            </dd>
          </div>
          <div>
            <dt>Generated</dt>
            <dd>{formatTimestamp(status.generatedAt)} UTC</dd>
          </div>
          <div>
            <dt>Source version</dt>
            <dd>{status.sourceVersion}</dd>
          </div>
          <div>
            <dt>Formula version</dt>
            <dd>{status.formulaVersion ?? "Not supplied"}</dd>
          </div>
          <div>
            <dt>Pipeline run</dt>
            <dd>{status.pipelineRunId ?? "Not supplied"}</dd>
          </div>
          <div>
            <dt>Manifest schema</dt>
            <dd>{status.manifestSchemaVersion}</dd>
          </div>
        </dl>
      </section>

      <section className="status-validation" aria-labelledby="status-validation-title">
        <div className="status-section-heading">
          <span>Validation summary</span>
          <h2 id="status-validation-title">
            {status.bundleCount} declared bundles
          </h2>
          <p>{status.validationSummary}</p>
        </div>
        <div className="status-checks">
          {status.checks.map((check) => (
            <article key={check.id}>
              <span
                className={`status-check-mark status-check-${check.status}`}
                aria-hidden="true"
              />
              <div>
                <small>{check.status.replaceAll("_", " ")}</small>
                <h3>{check.label}</h3>
                <p>{check.detail}</p>
                <div className="status-check-flags">
                  <span>{check.required ? "Required" : "Optional"}</span>
                  <span>{check.blocking ? "Blocking" : "Non-blocking"}</span>
                </div>
                {check.numerator !== undefined &&
                check.denominator !== undefined ? (
                  <p className="status-check-coverage">
                    <strong>
                      {check.numerator} of {check.denominator}
                    </strong>
                    {check.percentage !== undefined ? (
                      <span>{check.percentage.toFixed(1)}%</span>
                    ) : null}
                  </p>
                ) : check.percentage !== undefined ? (
                  <p className="status-check-coverage">
                    <span>{check.percentage.toFixed(1)}%</span>
                  </p>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="status-manifest" aria-labelledby="status-manifest-title">
        <div className="status-section-heading">
          <span>SHA-256 integrity</span>
          <h2 id="status-manifest-title">Manifest bundle inventory</h2>
          <p>
            Hashes verify the exact bytes read by the server registry. Expand
            the inventory to review each public bundle.
          </p>
        </div>
        <details>
          <summary>
            Show {manifest.entries.length} manifest entries
            <span>{manifest.schemaVersion}</span>
          </summary>
          <div className="manifest-table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Bundle</th>
                  <th scope="col">Records</th>
                  <th scope="col">Schema</th>
                  <th scope="col">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {manifest.entries.map((entry) => (
                  <tr key={`${entry.family}:${entry.id ?? "index"}`}>
                    <th scope="row" data-label="Bundle">
                      {entry.family}
                      {entry.id ? <small>{entry.id}</small> : null}
                    </th>
                    <td data-label="Records">{entry.recordCount}</td>
                    <td data-label="Schema">{entry.schemaVersion}</td>
                    <td data-label="SHA-256">
                      <code>{entry.sha256}</code>
                      <CopyHashButton
                        hash={entry.sha256}
                        bundleLabel={`${entry.family}${entry.id ? ` ${entry.id}` : ""}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <section className="status-limitations" aria-labelledby="status-limitations-title">
        <div className="status-section-heading">
          <span>Known limitations</span>
          <h2 id="status-limitations-title">What this publication does not claim</h2>
        </div>
        <ol>
          {status.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ol>
        <nav aria-label="Data status documentation">
          <Link href="/methodology">Read Methodology</Link>
          <Link href="/reports">Open Reports</Link>
        </nav>
      </section>
    </div>
  );
}
