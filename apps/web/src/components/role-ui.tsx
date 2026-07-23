import type { RoleFinding, TeamSnapshot } from "@/lib/types";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const signedPoints = (value?: number) => `${(value ?? 0) > 0 ? "+" : ""}${(value ?? 0).toFixed(1)} pp`;

export function ShareBar({ value, tone = "teal" }: { value: number; tone?: "teal" | "amber" | "coral" }) {
  return (
    <span className="share-track" aria-label={`${percent(value)} share`}>
      <span className={`share-fill share-fill-${tone}`} style={{ width: `${Math.min(value * 100, 100)}%` }} />
    </span>
  );
}

export function LeadFinding({ finding }: { finding: RoleFinding }) {
  return (
    <article className="lead-story panel">
      <div className="eyebrow">What changed this week</div>
      <div className="lead-grid">
        <div>
          <span className="team-chip">{finding.team} · {finding.position}</span>
          <h1>{finding.playerName} took control of the backfield.</h1>
          <p className="lead-copy">
            His documented team share moved from <strong>{percent(finding.priorShare ?? 0)}</strong> to
            <strong> {percent(finding.currentShare)}</strong> in the selected comparison window.
          </p>
          <div className="evidence-line">
            <span>Current evidence</span>
            <strong>{finding.currentRaw} of {finding.currentTeamTotal} opportunities</strong>
          </div>
        </div>
        <div className="change-visual" aria-label="Previous versus current role share">
          <div className="change-column muted">
            <small>Previous</small>
            <strong>{percent(finding.priorShare ?? 0)}</strong>
            <ShareBar value={finding.priorShare ?? 0} tone="amber" />
            <span>{finding.priorRaw} / {finding.priorTeamTotal}</span>
          </div>
          <span className="change-arrow" aria-hidden="true">→</span>
          <div className="change-column">
            <small>Current</small>
            <strong>{percent(finding.currentShare)}</strong>
            <ShareBar value={finding.currentShare} />
            <span>{finding.currentRaw} / {finding.currentTeamTotal}</span>
          </div>
          <div className="change-badge positive">{signedPoints(finding.changePoints)}</div>
        </div>
      </div>
    </article>
  );
}

export function MovementFeed({ findings }: { findings: RoleFinding[] }) {
  return (
    <section className="panel feed-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Role movement feed</span>
          <h2>Latest material changes</h2>
        </div>
        <a href="/reports/movement">View all</a>
      </div>
      <div className="movement-list">
        {findings.map((finding) => {
          const isUp = finding.direction === "up";
          return (
            <a className="movement-row" href={`/players/${finding.playerId}`} key={finding.id}>
              <span className={`direction ${isUp ? "positive" : "negative"}`}>{isUp ? "↑" : "↓"}</span>
              <span className="movement-player">
                <strong>{finding.playerName}</strong>
                <small>{finding.team} · {finding.position}</small>
              </span>
              <span className="movement-values">
                <strong>{percent(finding.priorShare ?? 0)} → {percent(finding.currentShare)}</strong>
                <small>{finding.label}</small>
              </span>
              <span className={isUp ? "positive" : "negative"}>{signedPoints(finding.changePoints)}</span>
            </a>
          );
        })}
      </div>
    </section>
  );
}

export function Rankings({ findings }: { findings: RoleFinding[] }) {
  return (
    <section className="panel rankings-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Backfield Control</span>
          <h2>Highest team opportunity shares</h2>
        </div>
        <a href="/reports/backfield">Full report</a>
      </div>
      <div className="ranking-table" role="table" aria-label="Backfield control rankings">
        {findings.map((finding, index) => (
          <a className="ranking-row" href={`/players/${finding.playerId}`} key={finding.id} role="row">
            <span className="rank">{String(index + 1).padStart(2, "0")}</span>
            <span className="ranking-player">
              <strong>{finding.playerName}</strong>
              <small>{finding.team} · {finding.position}</small>
            </span>
            <span className="ranking-share">
              <strong>{percent(finding.currentShare)}</strong>
              <ShareBar value={finding.currentShare} />
            </span>
            <span className="ranking-count">{finding.currentRaw} / {finding.currentTeamTotal}</span>
          </a>
        ))}
      </div>
    </section>
  );
}

export function TeamCard({ snapshot }: { snapshot: TeamSnapshot }) {
  return (
    <section className="panel team-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Team depth</span>
          <h2>{snapshot.name}</h2>
        </div>
        <a href={`/teams/${snapshot.team.toLowerCase()}`}>Open team</a>
      </div>

      <div className="team-columns">
        <div>
          <h3>Backfield</h3>
          {snapshot.backfield.map((row) => (
            <div className="team-row" key={row.playerName}>
              <span>{row.playerName}</span>
              <ShareBar value={row.share} />
              <strong>{percent(row.share)}</strong>
            </div>
          ))}
        </div>
        <div>
          <h3>Target hierarchy</h3>
          {snapshot.targets.map((row) => (
            <div className="team-row" key={row.playerName}>
              <span>{row.playerName}</span>
              <ShareBar value={row.share} tone="amber" />
              <strong>{percent(row.share)}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
