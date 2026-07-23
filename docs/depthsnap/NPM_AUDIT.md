# DepthSnap web npm audit

Last reviewed: July 23, 2026

Scope: `apps/web`

Command:

```text
npm audit --json
```

## Current result

The audit reports three high-severity package findings and no critical findings:

| Package | Relationship | Advisory context |
| --- | --- | --- |
| `next` | Direct dependency | Aggregate finding through `postcss` and `sharp` |
| `postcss` | Transitive dependency | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) and [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q) |
| `sharp` | Transitive dependency | [GHSA-f88m-g3jw-g9cj](https://github.com/advisories/GHSA-f88m-g3jw-g9cj) |

The installed application version is Next.js `16.2.11`. The audit currently
offers Next.js `9.3.3` as its automated fix, which is a major downgrade and is
not appropriate for this application. No dependency versions were changed as
part of the Playwright CI reliability correction.

Reassess these findings when the Next.js dependency graph offers a compatible,
tested upgrade path.
