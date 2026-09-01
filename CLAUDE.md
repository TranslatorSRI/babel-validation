# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Babel Validation is a test suite and web tools for validating outputs from [Babel](https://github.com/TranslatorSRI/Babel), which powers the Translator [Node Normalization (NodeNorm)](https://nodenorm.transltr.io/docs) and [Name Resolver (NameRes)](https://name-lookup.transltr.io/docs) services.

## Commands

### Python Tests (primary)

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Run from repo root:

```bash
# With -n (xdist), always pass the tests path explicitly (`pytest tests -n 8 ...`):
# without it, workers do not load tests/conftest.py early enough to know the
# custom options, and every worker dies at argparse — or collects nothing.
pytest --target dev                    # Run all tests against dev environment (default if no --target)
pytest --target prod                   # Run against production
pytest --target dev --target prod      # Run against multiple targets
pytest --target all                    # Run against all targets in targets.ini
pytest --category "Unit Tests"         # Filter by Google Sheet category
pytest --category-exclude "Slow"       # Exclude a category
pytest tests/nodenorm/test_nodenorm_from_gsheet.py  # Run a specific test file
# Run a specific test row: -k rejects '=' in its expression, so use the full node ID
# (the target name's position in the parametrize id varies; ask pytest with --collect-only -q)
pytest "tests/nodenorm/test_nodenorm_from_gsheet.py::test_normalization[test_nodenorm_from_gsheet.test_row:row=42-dev]"
```

### Code Formatting

```bash
black tests/    # Format Python test code
```

Note that the repository is *not* currently black-clean — `black --check tests/ src/` reports
~30 files it would reformat. Running `black` across the tree would bury a real change in
unrelated churn, so format only the files you touch, or match the surrounding style.

### Dashboard Website (website/)

```bash
cd website && npm install && npm run dev   # Dev server at localhost:4321/babel-validation/
npm run build                              # astro check + production build
npm test                                   # vitest: the Vue components' URL/filter/pagination logic
npm run fetch-data                         # download the published report.json/history.jsonl
```

The dashboard fetches `data/report.json` and `data/history.jsonl`, which are gitignored.
`npm run fetch-data` downloads the live site's copies into `website/public/data/` — the
quickest way to get real data for frontend work. To make them from scratch instead, run
`pytest --report-jsonl` plus `uv run python -m src.babel_validation.tools.generate_report`
(see README).

CI installs with `npm ci`, which is far stricter than the `npm install` you run locally: it
refuses a lockfile that does not match `package.json`, and it fails on platform-specific
packages that npm 11 writes into the lock without `optional: true` when the runner's npm is
10 (`EBADPLATFORM` on an Android build of lightningcss). Both workflows therefore pin
`node-version: 24`. After changing any dependency, run `npm ci` locally — not just
`npm test` — or the failure surfaces only on the runner, and in `dashboard.yaml` it surfaces
four hours in, at the build step, after every test has been paid for.

Beware: the root `.gitignore`'s Python-template `lib/` pattern matches *any* directory named
`lib`, including under `website/src/` — a file there builds locally but never reaches CI.
Check `git status` shows new frontend files as tracked.

## Architecture

### Library (`src/babel_validation/`)

Shared library code used by the tests and potentially other consumers.

- `core/testrow.py` — `TestRow` dataclass (models a single Google Sheet test row), `TestStatus` enum, `TestResult` dataclass
- `services/nodenorm.py` — `CachedNodeNorm`: wraps the NodeNorm `get_normalized_nodes` API with per-instance caching
- `services/nameres.py` — `CachedNameRes`: wraps the NameRes `lookup`/`bulk-lookup` APIs with per-instance caching
- `sources/google_sheets/google_sheet_test_cases.py` — `GoogleSheetTestCases`: downloads and parses the shared Google Sheet into `TestRow` instances and pytest `ParameterSet` lists

### Test Framework (`tests/`)

The core of this project. Tests validate NodeNorm and NameRes services across multiple deployment environments.

**Target system:** `tests/targets.ini` defines endpoints for each environment (dev, prod, test, ci, exp, localhost). Tests use `target_info` fixture to get URLs. The `conftest.py` parametrizes tests across targets via `--target` CLI option; default is `dev`.

**Google Sheet integration:** ~2000+ test cases are pulled from the shared Babel Validation
Google Sheet. Its ID comes from the `BABEL_VALIDATION_SHEET_ID` environment variable (`.env`
locally, a repository secret in Actions) and is deliberately not checked in.
`src/babel_validation/sources/google_sheets/google_sheet_test_cases.py` fetches and parses
the rows into `TestRow` dataclasses. Rows marked as not expected to pass are wrapped with `pytest.mark.xfail(strict=True)`. Tests are parametrized by row, with IDs like `gsheet:row=42`.

**Category filtering:** Google Sheet rows have a Category column. The `test_category` fixture (from conftest.py) returns a callable that tests use to `pytest.skip()` rows not matching `--category`/`--category-exclude` filters.

**Test modules:**
- `tests/nodenorm/` — NodeNorm tests (normalization accuracy, preferred IDs/labels, Biolink types, conflation, descriptions, OpenAPI spec, setid endpoint)
- `tests/nameres/` — NameRes tests (label lookup, autocomplete, Biolink type filtering, blocklist, taxon_specific flag)
- `tests/nodenorm/by_issue/` — Per-issue regression tests for NodeNorm (hand-written)

### Dashboard Website

- **`website/`** — Astro + Vue site deployed to GitHub Pages
  (https://translatorsri.github.io/babel-validation/). Three pages under one `Layout.astro`
  shell (nav bar, cards on a tinted page, `data-bs-theme` dark mode, all custom CSS in
  `src/styles/theme.css`): `/` renders the environment cards, the promotion-drift panel and
  the `/status` matrix from `report.json`; `/results/` renders the tests-by-environment
  matrix behind a sticky filter bar; `/history/` renders `history.jsonl` plus a diff against
  the previous run. Everything about the report that is not markup — link builders, labels,
  the interestingness predicate — lives in `src/reportData.js`. Regenerated daily by `.github/workflows/dashboard.yaml`: pytest per target with
  `--report-jsonl` (a `pytest_runtest_logreport` hook in `tests/conftest.py`), then
  `src/babel_validation/tools/generate_report.py` aggregates the raw outcomes, fetches each
  target's `/status`, and writes both data files into `website/public/data/`.
- **`scala-validation/`** — Legacy, unmaintained

## Untrusted Input

Most of what this project reads was written by someone else and reviewed by nobody. Treat it as
hostile, not merely as data that might be malformed:

- **GitHub issue bodies** (`src/babel_validation/sources/github/`) — anyone with a GitHub account
  can write one, and we parse it into live NodeNorm/NameRes calls.
- **The Google Sheet** (`src/babel_validation/sources/google_sheets/`) — anyone with edit access.
- **Anything off the network**, including a service's response.

`tests/targets.ini` is the exception: its URLs and its `Repositories` list are checked-in config,
so they are trusted, and guards belong on what the issue supplies rather than on them.

Every failure mode below was real, and found in this code. These are the shapes to look for.

**A regex over untrusted text can hang the process.** `\s+ .*? \s+` before a literal is three
nested backtracking quantifiers, and matched in cubic time: 53s on an 8KB body, hours at GitHub's
65536-character limit. Avoid adjacent quantifiers that can match the same characters — anchor on
something disjoint, such as a newline or a literal. Note that `pytest --timeout` only wraps test
execution, so anything running at **collection** time has no timeout at all.

**`yaml.safe_load` is not a safe parser, only a non-executing one.** It still resolves anchors,
aliases and merge keys, and PyYAML shares the aliased nodes rather than copying them — so the load
looks cheap and the blow-up lands on whatever formats the result afterwards. 337 bytes became a
25MB error message. Use `_NoAliasSafeLoader` in `sources/github/github_issues_test_cases.py`.

**Format untrusted text with `%r` / `!r`, never `%s` / `{}`.** `repr()` escapes exactly the
characters `str.isprintable()` rejects — ANSI escapes, C0/C1 controls, bidi overrides, zero-width
characters — so it is the whole defence for anything reaching a terminal, a log line or a pytest
ID. Truncate before `repr()`ing anything that might be large: the message is kept in pytest's
report.

**A guard that runs after the value was logged is too late.** Validate at the one choke point that
sees every value before anything formats it. For assertion params that is
`AssertionHandler._rejection()`, because the per-handler CURIE check skips whatever
`curie_params()` excludes and is turned off entirely by `VALIDATE_CURIES = False`.

**Never let outside text choose what we fetch.** `get_issues_by_ids()` takes an ID that decides
which repository we read assertions from, and its `[^#]+` group admits slashes — so check the
allowlist *before* the call, or the value reaches the GitHub API as a URL path.

**Fail loudly; skipping looks like passing.** Reject a bad issue rather than silently running a
truncated part of it. The same goes for missing credentials: the GitHub issue tests *skip* without
a token, so a green run may have tested nothing.

**The dashboard publishes untrusted text on a public website.**
`src/babel_validation/tools/generate_report.py` is the choke point between the raw pytest
outcomes and `report.json`: it repr-escapes and truncates all text, passes `/status`
responses through a key whitelist, only emits issue ids and source URLs that match the
`targets.ini` `Repositories` allowlist, and withholds blocklist test details entirely (that
sheet may not be public — do not add `ids=` to the blocklist parametrize or link to it).
The Vue components must render report values with `{{ }}` interpolation only — never
`v-html` — and construct links from validated parts (allowlisted `org/repo#N`,
`targets.ini` URLs), never verbatim from report text. A facet is as public as a cell: the
filter bar's category and source dropdowns are built from report values, so they exclude
blocklist rows exactly as the table does. Anything that aggregates over `results` needs the
same check.

**Never leak the Google Sheet ID or the GitHub token.** The report, the website, and any
Git commit must not contain the test-case sheet's ID or a link to either sheet — casual
observers of the public site must not be able to find them, and the ID is the capability
that grants access (the sheets are shared as "anyone with the link", because the CSV fetch
is unauthenticated). The IDs live only in the `BABEL_VALIDATION_SHEET_ID` and
`BABEL_VALIDATION_BLOCKLIST_SHEET_ID` environment variables (`.env` locally — gitignored —
and repository secrets in Actions), resolved through
`src/babel_validation/sources/google_sheets/resolve_sheet_id()`. Refer to it as the
"Babel Validation Google Sheet"; sheet *content* (row numbers, queried/expected CURIEs and
labels, category, source — often a GitHub issue link) is fine to publish once it passes the
generator's validation. The sheet is expected to be fully replaced by the GitHub issue
system over the next few months, at which point it can be removed from this repo entirely.

**Do not read `.env`, and do not print the variables it sets.** Everything a coding agent
reads goes into a transcript that is stored, replayed and pasted into issues, so `cat .env`,
`Read`ing it, `grep`ping it, `echo $BABEL_VALIDATION_SHEET_ID` or printing a CSV export URL
turns a secret into a logged one. This holds even when the user asks for help with the
values: `env.default` documents every variable, so there is no reason to look at the filled-in
copy. Writing is fine — `cp env.default .env`, or appending a line the user dictates — it is
reading back that leaks. To check whether something is set without revealing it, print a
boolean and nothing else:

```bash
uv run python -c "import os, dotenv; dotenv.load_dotenv(); print('BABEL_VALIDATION_SHEET_ID' in os.environ)"
```

If a value does end up in the transcript, say so plainly rather than carrying on: the sheet is
shared as "anyone with the link", so an exposed ID means re-sharing that sheet under a new ID
and rotating the repository secret.

**Caches belong in `cache_dir()`** (`src/babel_validation/core/__init__.py`), a 0700 directory
under the user's home — never a fixed name in the shared temp directory. On a CI runner or a
shared machine anyone can pre-create such a file, and the issue cache decides what a later run
fetches and executes.

## Key Dependencies

- Python >=3.11, pytest, requests, deepdiff, openapi-spec-validator, black
- `uv` for Python dependency management (no requirements.txt — uses pyproject.toml)

## Testing Patterns

When writing new tests:
- Use the `target_info` fixture to get NodeNorm/NameRes URLs from targets.ini
- For Google Sheet-based tests, parametrize with `gsheet.test_rows()` and use the `test_category` fixture for category filtering
- Use `pytest.mark.xfail(strict=True)` for known failures (strict=True means unexpected passes also fail)
- Hand-written per-issue regression tests go in `tests/nodenorm/by_issue/`
- **`pytest tests/github_issues` is expected to be red, and that is the tool working.** An open
  issue whose assertions all pass is a strict XPASS, meaning it looks closeable; a closed issue
  with failing assertions means it looks like it should be reopened. Those results are findings
  about Babel, not defects in this repo — do not "fix" them by editing the assertions. Only a
  hard ERROR (an unknown assertion name, a rejected issue body) is a problem here.
- When checking that a new test really fails without its fix, **clear `__pycache__` between runs**.
  A same-length edit (`%r` for `%s`, say) leaves the source's size unchanged, and if the mtime lands
  in the same granularity the `.pyc` is not invalidated — so the mutation appears to pass a test
  that never saw it. Also avoid asserting on `caplog.text` for anything about control characters:
  it does not carry them through, so such a test passes whatever the code does. Read
  `caplog.records` and `getMessage()` instead.
- **Never put a complete `{{BabelTest|...}}` marker or a fenced `babel_tests:` block into a GitHub
  issue you file** — not even in prose explaining the syntax. `TranslatorSRI/babel-validation` is
  itself in the scanned `Repositories` list, so the harness collects the marker and runs it: an
  issue that merely *describes* an assertion becomes a test of that assertion. Because a new issue
  is open, an assertion that passes then reports as a strict XPASS failure. This is not
  hypothetical — issue #115 was filed with a marker in it and immediately failed the live suite.
  Quote a partial marker instead, dropping the closing `}}`, which the pattern needs to match. A
  one-line ```` ```yaml babel_tests: ``` ```` in prose is already safe: the block pattern requires a
  newline after the key.
- To check behaviour when no GitHub token is available, run with `GITHUB_TOKEN=` (set but
  empty) rather than unsetting it: `dotenv.load_dotenv()` will not override a key already
  present in `os.environ`, so this defeats the token in the developer's `.env` file
- **Validate an OpenAPI document with `validate(parsed_json, base_uri=url)`, never
  `validate_url(url)`.** `validate_url` re-fetches the URL and reads it as YAML, and YAML 1.1 needs
  both a `.` and a signed exponent in a float — so NodeNorm's `1e-06` parses as the *string*
  `'1e-06'` and the validator reports `'1e-06' is not of type 'number'` against JSON that is
  perfectly valid. The spurious error is also first, so it masks the real one further down the
  document.
- **A new unit test needs `pytestmark = pytest.mark.unit`, or CI never runs it.** The only pytest
  job in `tests.yaml` is `pytest -m unit`, so an unmarked file is silently deselected — it looks
  like a passing suite while testing nothing. This is not hypothetical: `test_milestones_page.py`
  in #112 had six tests that had never run.
- Import shared classes from `src.babel_validation.*` (e.g. `from src.babel_validation.services.nodenorm import CachedNodeNorm`)
