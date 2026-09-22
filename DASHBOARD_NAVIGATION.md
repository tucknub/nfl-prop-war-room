# Dashboard Navigation

This file describes the current PropWar navigation. `dashboard/app.py` is the source of truth if this document and the application ever disagree.

## Owner workflow

The owner experience is intentionally narrow.

### PropWar

1. **Today** - current actions that clear PropWar's trust and freshness rules.
2. **Players** - player role usage, role movement, and supporting evidence.
3. **Markets** - current sportsbook comparison, verification queues, arbs, middles, glitches, and +EV research.
4. **Fantasy** - live read-only Sleeper team, lineup, waiver, matchup, trade, and league context.

### More

- **Teams** - team-level role evidence.
- **Reports** - packaged role reports.
- **Games** - game-level supporting context.
- **Advanced Research** - hidden advanced role-query workspace.
- **Market Research** - hidden full-prop research workspace.
- **PDL** - Point Differential League decision workspace.
- **Knockout** - ESPN-backed elimination fantasy workspace.
- **Methodology** - data definitions, calculations, and trust boundaries.

## Public role-intelligence workflow

Public users see the factual role-research surfaces only:

- Home
- Reports
- Teams
- Players
- Games
- Advanced Research
- Methodology

Owner-only sportsbook, fantasy, PDL, and Knockout workspaces are not public fallbacks.

## Trust rules

- Current-season role evidence must pass the publication gates before it is treated as current.
- Markets must distinguish a genuine zero-signal result from provider failure or insufficient coverage.
- Full prop quotes must satisfy the current freshness contract before use.
- Model outputs, baselines, signals, and FAAB estimates must remain labeled as estimates rather than facts.
- Missing source, identity, freshness, or coverage should fail closed instead of creating an all-clear.

See `docs/propwar/TRUST_CONTRACT.md` for the detailed product contract.

## Legacy and hidden research

Older Signal Command Center, Position Signal Board, historical-test model boards, and readiness experiments are legacy research. They are not the current product workflow and should not be restored to primary navigation without a new product decision.

`dashboard/pages/90_Admin_Research.py` remains intentionally hidden. It preserves legacy experiments and validation artifacts only. It is not the source of truth for current RB, WR, or TE role status.

## Product principle

Do not add another primary tab simply because a research surface exists. Prefer feeding validated evidence into Today, Players, Markets, Fantasy, PDL, or Knockout. Keep advanced evidence under More or hidden until it earns a primary workflow role.
