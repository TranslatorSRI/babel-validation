# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Babel Validation is a test suite and web tools for validating outputs from [Babel](https://github.com/TranslatorSRI/Babel), which powers the Translator [Node Normalization (NodeNorm)](https://nodenorm.transltr.io/docs) and [Name Resolver (NameRes)](https://name-lookup.transltr.io/docs) services.

## Commands

### Python Tests (primary)

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Run from repo root:

```bash
pytest --target dev                    # Run all tests against dev environment (default if no --target)
pytest --target prod                   # Run against production
pytest --target dev --target prod      # Run against multiple targets
pytest --target all                    # Run against all targets in targets.ini
pytest --category "Unit Tests"         # Filter by Google Sheet category
pytest --category-exclude "Slow"       # Exclude a category
pytest tests/nodenorm/test_nodenorm_from_gsheet.py  # Run a specific test file
pytest tests/nodenorm/test_nodenorm_from_gsheet.py -k "row=42"  # Run a specific test row
```

### Code Formatting

```bash
black tests/    # Format Python test code
```

Note that the repository is *not* currently black-clean — `black --check tests/ src/` reports
~30 files it would reformat. Running `black` across the tree would bury a real change in
unrelated churn, so format only the files you touch, or match the surrounding style.

### Vue Website (website-vue3-vite/)

```bash
cd website-vue3-vite && npm install && npm run dev     # Dev server
npm run build     # Production build
npm run lint      # ESLint + auto-fix
npm run test:unit # Vitest unit tests
```

### Astro Documentation Site (website/)

```bash
cd website && npm install && npm run dev   # Dev server at localhost:4321
```

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

**Google Sheet integration:** ~2000+ test cases are pulled from a [shared Google Sheet](https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/). `src/babel_validation/sources/google_sheets/google_sheet_test_cases.py` fetches and parses these into `TestRow` dataclasses. Rows marked as not expected to pass are wrapped with `pytest.mark.xfail(strict=True)`. Tests are parametrized by row, with IDs like `gsheet:row=42`.

**Category filtering:** Google Sheet rows have a Category column. The `test_category` fixture (from conftest.py) returns a callable that tests use to `pytest.skip()` rows not matching `--category`/`--category-exclude` filters.

**Test modules:**
- `tests/nodenorm/` — NodeNorm tests (normalization accuracy, preferred IDs/labels, Biolink types, conflation, descriptions, OpenAPI spec, setid endpoint)
- `tests/nameres/` — NameRes tests (label lookup, autocomplete, Biolink type filtering, blocklist, taxon_specific flag)
- `tests/nodenorm/by_issue/` — Per-issue regression tests for NodeNorm (hand-written)

### Web Applications

- **`website-vue3-vite/`** — Active Vue 3 + Vite app that fetches test cases from the same Google Sheet and runs them against multiple endpoints in the browser
- **`website/`** — Newer Astro-based site deployed to GitHub Pages with prefix comparator and autocomplete tools
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
- Import shared classes from `src.babel_validation.*` (e.g. `from src.babel_validation.services.nodenorm import CachedNodeNorm`)
