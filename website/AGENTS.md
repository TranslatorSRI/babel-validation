# AGENTS.md — the dashboard website

Instructions for working on the Astro + Vue dashboard. The repository-wide rules in the root
`AGENTS.md` still apply — in particular its "Untrusted Input" section, which this file
extends for the frontend. `README.md` here describes the pages and where their data comes
from.

## Commands

```bash
cd website && npm install && npm run dev   # Dev server at localhost:4321/babel-validation/
npm run build                              # astro check + production build
npm test                                   # vitest: the Vue components' URL/filter/pagination logic
npm run fetch-data                         # download the published report.json/history.jsonl
```

The dashboard fetches `data/report.json` and `data/history.jsonl`, which are gitignored.
`npm run fetch-data` downloads the live site's copies into `website/public/data/` — the
quickest way to get real data for frontend work. To make them from scratch instead, run
`pytest --report-jsonl` plus `uv run python -m babel_validation.tools.generate_report`
(see the root README).

Two CI traps you can hit without opening a file here — `npm ci` refusing a lockfile, and the
root `.gitignore` swallowing any directory named `lib` — are in the root `AGENTS.md`, under
"Dashboard Website (website/)".

## Rendering untrusted report values

Everything in `report.json` started as untrusted text. `generate_report.py` escapes and
validates it before it is written (see the root `AGENTS.md`), and the components must not
undo that:

**Render report values with `{{ }}` interpolation only — never `v-html`** — and construct
links from validated parts (allowlisted `org/repo#N`, `targets.ini` URLs), never verbatim
from report text. The root `AGENTS.md`'s rule that anything aggregating over `results`
excludes blocklist rows covers the filter bar's category and source dropdowns too: a facet is
as public as a cell.

**A query parameter must never index a JSON-parsed object directly.** `report.results` and
each result's `outcomes` are plain objects, so they inherit `Object.prototype`: `?test=`,
`?env=` or any other URL-supplied key can name `constructor`, `toString` or `valueOf` and
come back truthy with none of the fields the code expects. This has now been two separate
bugs in `Results.vue` — one pinned an `Object.prototype` member as a table row, the other
made the environment filter match *every* row instead of none. Guard with `Object.hasOwn`
before the lookup. An allowlist is not available here: these parameters are read in
`readUrl()` before the report has loaded, so the set of valid values is not yet known.
