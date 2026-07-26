# DepthSnap web npm audit

Last reviewed: July 26, 2026

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
| `postcss` | Transitive dependency | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93), [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q), and [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) |
| `sharp` | Transitive dependency | [GHSA-f88m-g3jw-g9cj](https://github.com/advisories/GHSA-f88m-g3jw-g9cj) |

The installed application version is Next.js `16.2.11`. The audit currently
offers Next.js `9.3.3` as its automated fix, which is a major downgrade and is
not appropriate for this application. Next.js `16.2.12` still declared the
same PostCSS and Sharp versions when this gate was run.

PostCSS processes repository-owned CSS at build time. The application accepts
no untrusted CSS or image input, Next image optimization is disabled, and the
provider-neutral production package removes both PostCSS and Sharp. Its
production smoke suite passes after their removal. The findings are therefore
accepted as build-environment risk pending a compatible tested Next.js update;
they are not shipped runtime packages.

Reassess these findings when the Next.js dependency graph offers a compatible,
tested upgrade path.
