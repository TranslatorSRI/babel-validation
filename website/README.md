# Babel Validation dashboard

The site published at <https://translatorsri.github.io/babel-validation/>. It shows the result of
running this repository's validation suite against every NodeNorm and NameRes deployment, once a
day, so that a failure can be read against where it sits in the promotion pipeline: a test that
fails in prod but passes everywhere else is a different problem from one that fails everywhere.

Astro for the pages and the build, Vue islands for the parts that filter and sort, Bootstrap 5.3
with a small theme layer in `src/styles/theme.css`.

## Pages

| Page | What it answers |
| --- | --- |
| `/` | Is anything wrong right now? Run banner, per-environment cards, promotion-drift patterns, and the environment detail matrix. |
| `/results/` | Which tests, exactly? The full matrix behind a sticky filter bar, filterable by outcome, category, source and environment, with the filter state in the URL so a view can be shared. |
| `/history/` | What changed since yesterday? A diff against the previous run, then one row per run. |

## Where the data comes from

Nothing here queries NodeNorm or NameRes. The site renders three files that
`.github/workflows/dashboard.yaml` regenerates daily and publishes to `gh-pages` alongside it:

- **`data/report.json`** — one entry per test, with an outcome per environment, plus each
  deployment's `/status`. Written by `src/babel_validation/tools/generate_report.py` from the JSONL
  that `pytest --report-jsonl` emits.
- **`data/history.jsonl`** — one summary line per run, appended to the previously published file.
- **`data/milestones.json`** — open milestones across the Babel repositories and their open
  issues. Written by `src/babel_validation/tools/generate_milestones.py` from the GitHub API,
  in a job of its own so the milestones page does not wait on the test suite or fail with it.

Any of the three may be a *carried-forward* copy: when a run fails to regenerate one, the
publish job refetches the last published version rather than let the cleaning deploy delete
the page. Each page renders its own `generated_at` for that reason.

To work against real data locally, `npm run fetch-data` downloads the published copies into
`public/data/`, which is gitignored. Or generate your own from a test run — see
`generate_report.py`'s header for the invocation.

## Commands

```sh
npm install       # or `npm ci` against the lockfile, which is what CI uses
npm run dev       # dev server at localhost:4321
npm run build     # production build into dist/
npm test          # vitest
```

CI runs `npm ci` and `npm test` on Node 24, matching the lockfile's npm version.

## Working on it

**Everything in the report is untrusted input.** It is built from GitHub issue bodies, Google Sheet
cells and service responses, none of which anyone reviewed. The generator validates and escapes it
server-side, but this site must also:

- render report values as text through `{{ }}` only — there is no `v-html` anywhere, and adding one
  is how this site would start executing what an issue author wrote;
- build links from validated parts, as `reportData.js` does, never from report text verbatim;
- keep blocklist rows withholding their detail, in the expanded-row markup as well as the label;
- never show a Google Sheet ID or a link to one of the sheets. They are repository secrets.

`src/reportData.js` holds everything about `report.json` that isn't rendering — fetching, labels,
the "interesting" predicate, the link builders — and is the right place for logic that would
otherwise be duplicated across two components. It is deliberately not in a `lib/` directory: the
root `.gitignore`'s Python-template `lib/` pattern silently swallows any directory of that name.

**The site is served under `<base href="/babel-validation/">`, and vitest is not.** A relative URL
passed to `history.pushState`/`replaceState` resolves against the *document base*, not the current
path, so `replaceState(null, '', '?q=1')` on `/results/` silently rewrites the address bar to the
site root — a different page, which ignores the parameters. Always build these from
`window.location.pathname`. No test can catch it: the suite mounts components at `/` with no
`<base>` element, so the relative form works there and fails only in production.

**Vue condenses whitespace at a `<template>` boundary, and a dropped separator looks like bad
data.** A trailing `" · "` inside a `<template v-if>` is a whitespace-only text node at the end of
the block, so it is removed: the summary line on `/milestones/` rendered `3 past due· as of
2026-09-01`, which reads as a generator bug rather than a template one. Put separators at the
*start* of each part instead of joining parts with them — a leading `·` has no boundary to be
eaten at. Assertions on `wrapper.text()` will not catch this unless they compare the whole string,
because the words are all still there.

`src/deploymentOrder.js` fixes the left-to-right order of every table. Environments read in
promotion order, so a value that differs from its left neighbour is a change on its way through.
