# PropWar Project Blueprint

## Product identity

PropWar is an **NFL Role & Usage Research** product. It presents factual historical role, opportunity, game-context, and participation information. It does not provide odds, betting recommendations, predictive role claims, or a universal player score.

## Product hierarchy

1. **Home** is the eventual weekly discovery surface.
2. **Teams, Players, Games, Reports, and Explorer** provide the supporting evidence needed to understand a displayed observation.
3. Methodology remains factual and inspectable without turning the public product into a validation report.

## Locked product boundaries

- No odds.
- No betting recommendations.
- No `PLAY`, `LEAN`, or `PASS` labels.
- No universal player score.
- No public claim that a role change is sustainable or persistent.
- RB carry-share and RB opportunity-share detectors remain private shadow research.
- WR and TE automated role-change detection remain retired.
- Sleeper is postponed.
- Opponent adjustment is excluded.
- Portrait usability is mandatory.

## Current production state

- Production branch: `streamlit-cloud-deploy`
- Production commit: `8b759f18c34708300acf5e3ef84d0e4cbbbde597`
- Rollback checkpoint: `production-streamlit-cloud-pre-mobile-ux-v2`
- Active phase: Phase A — Targeted Correctness Audit
- Production deployment during this phase: **not authorized**

## Change discipline

Audit findings may document defects and propose fixes. They do not alter locked product direction. New ideas belong in `PRODUCT_BACKLOG.md` until a later phase is explicitly authorized.
