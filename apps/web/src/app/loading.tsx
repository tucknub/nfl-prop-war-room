export default function Loading() {
  return (
    <div className="page-shell loading-shell" aria-busy="true" aria-label="Loading DepthSnap findings">
      <div className="fixture-notice skeleton skeleton-notice" />
      <div className="loading-lead">
        <div>
          <span className="skeleton skeleton-short" />
          <span className="skeleton skeleton-title" />
          <span className="skeleton skeleton-title skeleton-title-short" />
          <span className="skeleton skeleton-link" />
        </div>
        <div className="loading-evidence">
          <span className="skeleton skeleton-block" />
          <span className="skeleton skeleton-block" />
        </div>
      </div>
      <div className="loading-rows">
        {[0, 1, 2].map((row) => (
          <span className="skeleton skeleton-row" key={row} />
        ))}
      </div>
      <span className="sr-only">Loading findings</span>
    </div>
  );
}
