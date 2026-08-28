# PropWar Product Status

This file answers a different question than code coverage:

> **Can this surface be relied on as part of the actual product?**

Statuses should be updated from real usage during the 2026 season.

| Surface | Product role | Current status | Keep visible? | Finish condition |
| --- | --- | --- | --- | --- |
| Today | CORE | BETA / PROVING | Yes | Opens reliably, ranks a small useful set of cross-product actions, survives normal missing-source states, used repeatedly in live weeks |
| Players / Command Center | CORE | BETA / PROVING | Yes | Same-player role + market + fantasy context is current, identity-safe, fast, and useful during live weeks |
| Markets / Glitch Radar | CORE | USABLE / PROVING | Yes | Movement/history and action labels remain trustworthy through sustained live NFL market use |
| Fantasy / Fantasy HQ | CORE | BETA / PROVING | Yes | Normal weekly lineup/waiver/trade workflow is fast and repeatedly useful across live leagues |
| Teams | SUPPORT | USABLE ROLE EVIDENCE | More | Supports Players/role investigation without needing to act like a separate product |
| Reports | SUPPORT | USABLE ROLE EVIDENCE | More | Reports remain understandable, current, and linked from role workflows |
| Games | SUPPORT | USABLE ROLE EVIDENCE | More | Useful for game-level usage audit; not required as a primary destination |
| Advanced Research | SUPPORT | ADVANCED | More | Stays powerful without becoming normal-user navigation clutter |
| Market Research / Deep Prop Radar | SUPPORT | USABLE ADVANCED | More | Feeds Markets diagnostics; eventually fold more directly into Markets |
| Methodology | SUPPORT | DOCUMENTATION | More | Accurate explanation of current public role methodology |
| Margin War Room | PERSONAL | USABLE / SPECIALIZED | More | Reliable for the owner's live Margin pool |
| Knockout Fantasy | PERSONAL | BETA / SPECIALIZED | More | Proved during the actual elimination league |
| Admin Research | INTERNAL | HIDE | No | Never normal product navigation |
| Historical projection/model labs | INTERNAL / LEGACY | ARCHIVE / R&D | No | Kept for auditability/research, not presented as current product |

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

## Exit criteria for private beta

PropWar should not be called finished until all four core workspaces have:

- passed production-context startup tests
- acceptable normal interaction speed
- current-season data appropriate to the claim being made
- at least several weeks of real 2026 use
- documented failures/false positives reviewed
- a clear answer-first interface
- no requirement that the user understands repository/module boundaries
