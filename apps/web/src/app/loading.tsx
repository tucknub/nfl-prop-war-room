function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="skeleton-rows">
      {Array.from({ length: count }, (_, index) => (
        <span className="skeleton skeleton-row" key={index} />
      ))}
    </div>
  );
}

export default function Loading() {
  return (
    <div
      className="page-shell loading-shell"
      aria-busy="true"
      aria-label="Loading DepthSnap findings"
    >
      <div className="fixture-notice skeleton skeleton-notice" />
      <div className="dashboard-grid">
        <section className="dashboard-panel lead-panel skeleton-panel">
          <div className="skeleton-panel-heading">
            <span className="skeleton skeleton-label" />
          </div>
          <div className="skeleton-lead-body">
            <div>
              <span className="skeleton skeleton-avatar" />
              <span className="skeleton skeleton-title" />
              <span className="skeleton skeleton-title skeleton-title-short" />
              <span className="skeleton skeleton-action" />
            </div>
            <span className="skeleton skeleton-evidence-card" />
          </div>
        </section>

        <section className="dashboard-panel movement-panel skeleton-panel">
          <div className="skeleton-panel-heading">
            <span className="skeleton skeleton-label" />
          </div>
          <SkeletonRows count={3} />
        </section>

        <section className="dashboard-panel patterns-panel skeleton-panel">
          <div className="skeleton-panel-heading">
            <span className="skeleton skeleton-label" />
          </div>
          <SkeletonRows count={2} />
        </section>

        <section className="dashboard-panel reports-panel skeleton-panel">
          <div className="skeleton-panel-heading">
            <span className="skeleton skeleton-label" />
          </div>
          <SkeletonRows count={3} />
        </section>
      </div>
      <span className="sr-only">Loading findings</span>
    </div>
  );
}
