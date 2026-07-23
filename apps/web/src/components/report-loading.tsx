export function ReportLoading() {
  return (
    <div
      className="page-shell report-page-shell"
      aria-busy="true"
      aria-label="Loading report evidence"
    >
      <span className="skeleton report-loading-notice" />
      <div className="report-loading-header">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </div>
      <div className="report-loading-switcher">
        <span className="skeleton" />
        <span className="skeleton" />
        <span className="skeleton" />
      </div>
      <div className="report-loading-summary skeleton" />
      <div className="report-loading-rows">
        {Array.from({ length: 6 }, (_, index) => (
          <span className="skeleton" key={index} />
        ))}
      </div>
      <span className="sr-only">Loading report evidence</span>
    </div>
  );
}
