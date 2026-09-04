# PropWar Product Status

This file answers a different question than code coverage:

> **Can this surface be relied on as part of the actual product?**

Statuses should be updated from real usage during the 2026 season.

| Surface | Product role | Current status | Keep visible? | Finish condition |
| --- | --- | --- | --- | --- |
| Today | CORE | CONSOLIDATED / PROVING | Yes | Production-context startup passes; unaged no-key market preview is no longer promoted into Today; now needs repeated live-week proof that the remaining ranked action set is useful |
| Players / Command Center | CORE | CONSOLIDATED / PROVING | Yes | Production-context startup passes and exact identity safeguards are built; now needs same-season 2026 role + market use |
| Markets / Glitch Radar | CORE | VERIFICATION-FIRST / PROVING | Yes | Full prop quotes fail closed above 120 seconds or when undated; no-key preview is research-only; false-positive and provider-fair-value behavior still needs sustained live NFL proving |
| Fantasy / Fantasy HQ | CORE | CONSOLIDATED / PROVING | Yes | Production-context startup passes; heuristic FAAB bid recommendations and automatic season-long trade promotion were removed; weekly lineup/waiver/current-week-baseline usefulness still needs season proof |
| Teams | SUPPORT | USABLE ROLE EVIDENCE | More | Supports Players/role investigation without needing to act like a separate product |
| Reports | SUPPORT | USABLE ROLE EVIDENCE | More | Reports remain understandable, current, and linked from role workflows |
| Games | SUPPORT | USABLE ROLE EVIDENCE | More | Useful for game-level usage audit; not required as a primary destination |
| Advanced Research | SUPPORT | ADVANCED | More | Stays powerful without becoming normal-user navigation clutter |
| Market Research / Deep Prop Radar | SUPPORT | USABLE ADVANCED | More | Feeds Markets diagnostics; eventually fold more directly into Markets |
| Methodology | SUPPORT | DOCUMENTATION | More | Accurate explanation of current public role methodology |
| Margin War Room | PERSONAL | MODEL-LABELED / SPECIALIZED | More | Current spread is source-labeled; mean margin/loss/20+ values are explicitly historical/model estimates; continue live pool proving |
| Knockout Fantasy | PERSONAL | STRUCTURAL DECISION CENTER / PROVING | More | Decision-first state/roster/FAAB/released-roster workflow is built; prove it after the Sep. 3 draft and during live eliminations before adding survival probabilities or optimal-bid claims |
| Admin Research | INTERNAL | HIDE | No | Never normal product navigation |
| Historical projection/model labs | INTERNAL / LEGACY | ARCHIVE / R&D | No | Kept for auditability/research, not presented as current product |

## September 4, 2026 trust-hardening milestone

A repository-wide owner-workflow trust audit tightened market freshness and removed or relabeled unsupported certainty. The production state passed the full Product Gate with **827 tests passing** and every visible Streamlit page starting successfully. The governing standard is **[docs/propwar/TRUST_CONTRACT.md](docs/propwar/TRUST_CONTRACT.md)**.

## Current product call

PropWar is **not launch-ready for monetization**.

It is a **private beta** with four core workspaces and substantial supporting infrastructure.

The current priority order is:

1. Stability
2. Speed
3. 2026 current-season data
4. Consolidation
5. Daily-workflow proving
6. Evidence/action quality
7. Only then, new product capability

## What should be hidden rather than deleted

Do not delete useful research systems merely because they are not primary product surfaces.

Hide or demote:

- Admin Research
- legacy model-control pages
- experimental signal boards
- advanced diagnostics that duplicate a simpler user-facing answer
- specialty league tools from the primary navigation

The goal is a smaller **product**, not necessarily a smaller **repository**.

## Consolidation milestone — August 28, 2026

The product structure is now intentionally frozen around four owner workspaces:

- **Today**
- **Players**
- **Markets**
- **Fantasy**

Phase 1 and Phase 2 consolidation are merged. Home, Players, Markets, and Fantasy all pass production-like Streamlit startup checks from an external working directory.

The 2026 Current Role Operations workflow is also hardened for production Python 3.14 and an in-season Tuesday / Wednesday / Thursday retry cadence. It remains intentionally fail-closed until a complete regular-season week and all publication gates are available.

The remaining uncertainty is no longer whether the repository contains enough capability. The remaining uncertainty is whether the four core workflows prove useful and trustworthy during real 2026 NFL weeks.

See **[LIVE_PROVING_PLAN.md](LIVE_PROVING_PLAN.md)** for the operating plan.

## Exit criteria for private beta

PropWar should not be called finished until all four core workspaces have:

- passed production-context startup tests
- acceptable normal interaction speed
- current-season data appropriate to the claim being made
- at least several weeks of real 2026 use
- documented failures/false positives reviewed
- a clear answer-first interface
- no requirement that the user understands repository/module boundaries
