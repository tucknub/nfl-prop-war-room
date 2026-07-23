export function FixtureNotice({ children }: { children: string }) {
  return (
    <div className="fixture-notice" role="note">
      <span aria-hidden="true" />
      {children}
    </div>
  );
}
