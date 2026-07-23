"use client";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="page-shell">
      <section className="dashboard-panel home-state home-state-unavailable" role="alert">
        <div className="panel-heading">
          <span className="panel-label">Application error</span>
        </div>
        <div className="state-body">
          <span className="state-status">View unavailable</span>
          <h1>DepthSnap could not render this view</h1>
          <p>
            No replacement findings are shown. Try loading the validated bundle
            again.
          </p>
          <button type="button" onClick={reset}>
            Try again
          </button>
        </div>
      </section>
    </div>
  );
}
