# PropWar Product Definition

## One-sentence promise

**PropWar tells the owner what changed, what the market may have missed, and what action deserves attention.**

PropWar is an NFL decision-intelligence product, not a collection of unrelated dashboards.

## Core product

PropWar has four primary owner workspaces.

### 1. Today

**Question:** What matters right now?

Today composes the strongest existing outputs from the underlying tools into a small ranked action feed. It does not create a second prediction model.

Default owner goal:

- show a few actions, not dozens of tables
- explain why each surfaced
- show confidence/freshness
- deep-link to the tool that produced the evidence
- omit a source when its data is stale, missing, preseason-inappropriate, or otherwise unsafe

### 2. Players

**Question:** What changed with this player?

Players is the unified player workspace.

It combines, when safely identity-linked:

- canonical Role Intelligence
- Role Change Detector
- current team/context
- live market context
- best visible configured-book prices
- fantasy ownership
- selected-league status
- cross-league exposure

Historical role evidence and live market/fantasy context must remain clearly separated when they refer to different seasons.

### 3. Markets

**Question:** What is unusual or potentially mispriced right now?

Markets is the owner-facing market workspace.

The primary surface is Glitch Radar. Deep Prop Radar is supporting market research, not a second product.

Markets includes:

- best current opportunities
- Glitches
- +EV context
- line shopping
- movement/history
- alternate-ladder diagnostics
- line gaps
- near misses
- book coverage/freshness

Do not add more scanners unless a missing decision cannot be answered by the current stack.

### 4. Fantasy

**Question:** What should I do with my teams?

Fantasy is powered by Fantasy HQ.

It includes:

- ranked action center
- lineup decisions
- waivers
- FAAB
- roster health
- matchup/opponent context
- Manager Intelligence
- trade-fit evidence
- player ownership/availability
- cross-league exposure

Sleeper is the supported live provider. Yahoo/ESPN expansion is not a core priority until the existing workflow is proven during the season.

## Supporting surfaces

These are useful, but they are not primary product destinations.

### Role Intelligence evidence

- Teams
- Reports
- Games
- Advanced Research
- Methodology

These exist to explain and audit the player/team role engine.

### Specialized owner tools

- Margin War Room
- Knockout Fantasy War Room

These are private league utilities powered by PropWar infrastructure. They must not define the main product navigation.

### Advanced market research

- Deep Prop Radar

This is the diagnostic layer behind Markets. It should eventually be folded more directly into the Markets experience.

### Internal-only research

- Admin Research
- historical projection labs
- validation/control-room artifacts
- retired signal experiments

These are not product navigation.

## Definition of finished

A feature is not finished merely because code and tests exist.

A product surface is considered finished only when all of the following are true:

1. **Stable:** it opens reliably in the actual deployment environment.
2. **Current:** its actionable claims use appropriately current data.
3. **Understandable:** a user can tell what question the page answers without knowing the repository architecture.
4. **Actionable:** the page reaches a clear answer or explicitly says why it cannot.
5. **Evidence-backed:** every action can be traced to factual inputs.
6. **Fast enough:** normal interaction does not force unnecessary whole-app/network work.
7. **Season-proven:** the workflow has been used repeatedly during live 2026 NFL weeks.

Until season-proven, PropWar is a **private beta**.

## Product freeze

Until the four core workspaces are stable and season-proven, do not prioritize:

- new scanners
- new standalone dashboards
- new projection-model families
- AI chat
- Yahoo expansion
- ESPN integration
- additional specialty league tools
- generic research boards

New work should primarily fall into one of these categories:

- stability
- speed
- current data
- consolidation
- evidence quality
- action ranking
- usability

## Hosting strategy

### Phase 1 — finish on Streamlit

Use Streamlit as the current iteration/deployment environment while the product is still being simplified and season-tested.

Reasons:

- existing Python engines run natively
- current tests and operational workflows already target it
- fastest place to repair product/UX/data issues
- avoids combining a product redesign and hosting migration into one risky change

### Phase 2 — Cloudflare product shell

After the four core workflows are proven, move the product experience to Cloudflare:

- Cloudflare Workers + Static Assets for the frontend/full-stack shell
- Custom Domain for the branded PropWar URL
- Cloudflare storage/caching where appropriate
- preserve the existing Python analytics engines initially rather than rewriting model logic
- use a Container/API boundary for Python components that require the scientific Python runtime

The migration should be incremental. Do not rewrite validated role/fantasy/market engines merely to change hosting.

## Live-season proving

The product has moved from feature-building into proving mode.

See **[LIVE_PROVING_PLAN.md](LIVE_PROVING_PLAN.md)** for the weekly operating loop, issue severity rules, private-beta exit criteria, and the trigger for a later Cloudflare migration.

See **[PRODUCT_STATUS.md](PRODUCT_STATUS.md)** for the current surface-by-surface product status.

## Success criterion

Opening PropWar should no longer feel like entering a toolbox.

It should feel like:

> **Here are the few things that matter.**
>
> **Here is why.**
>
> **Here is where to inspect the evidence.**
