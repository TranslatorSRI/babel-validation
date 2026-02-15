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

### Test Framework (`tests/`)

The core of this project. Tests validate NodeNorm and NameRes services across multiple deployment environments.

**Target system:** `tests/targets.ini` defines endpoints for each environment (dev, prod, test, ci, exp, localhost). Tests use `target_info` fixture to get URLs. The `conftest.py` parametrizes tests across targets via `--target` CLI option; default is `dev`.

**Google Sheet integration:** ~2000+ test cases are pulled from a [shared Google Sheet](https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/). `tests/common/google_sheet_test_cases.py` fetches and parses these into `TestRow` dataclasses. Rows marked as not expected to pass are wrapped with `pytest.mark.xfail(strict=True)`. Tests are parametrized by row, with IDs like `gsheet:row=42`.

**Category filtering:** Google Sheet rows have a Category column. The `test_category` fixture (from conftest.py) returns a callable that tests use to `pytest.skip()` rows not matching `--category`/`--category-exclude` filters.

**Test modules:**
- `tests/nodenorm/` — NodeNorm tests (normalization accuracy, preferred IDs/labels, Biolink types, conflation, descriptions, OpenAPI spec, setid endpoint)
- `tests/nameres/` — NameRes tests (label lookup, autocomplete, Biolink type filtering, blocklist, taxon_specific flag)
- `tests/nodenorm/by_issue/` — Tests tied to specific GitHub issues
- `tests/common/` — Shared utilities (`GoogleSheetTestCases`, `TestRow`)

### Web Applications

- **`website-vue3-vite/`** — Active Vue 3 + Vite app that fetches test cases from the same Google Sheet and runs them against multiple endpoints in the browser
- **`website/`** — Newer Astro-based site deployed to GitHub Pages with prefix comparator and autocomplete tools
- **`scala-validation/`** — Legacy, unmaintained

## Key Dependencies

- Python >=3.11, pytest, requests, deepdiff, openapi-spec-validator, black
- `uv` for Python dependency management (no requirements.txt — uses pyproject.toml)

## Testing Patterns

When writing new tests:
- Use the `target_info` fixture to get NodeNorm/NameRes URLs from targets.ini
- For Google Sheet-based tests, parametrize with `gsheet.test_rows()` and use the `test_category` fixture for category filtering
- Use `pytest.mark.xfail(strict=True)` for known failures (strict=True means unexpected passes also fail)
- Issue-specific tests go in `tests/nodenorm/by_issue/` or `tests/github_issues/`
