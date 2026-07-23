"use client";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="page-shell">
      <section className="home-state home-state-unavailable" role="alert">
        <span className="section-kicker">Application error</span>
        <h1>DepthSnap could not render this view</h1>
        <p>
          No replacement findings are shown. Try loading the validated bundle
          again.
        </p>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </section>
    </div>
  );
}
