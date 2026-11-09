# AGENTS.md — writing tests

Rules for writing tests in this directory. The root `AGENTS.md` covers running them (the
pytest commands, targets, categories), the rules that apply whenever the suite runs or an
issue is filed, and "Untrusted Input", which applies to test code as much as library code.

When writing new tests:
- Use the `target_info` fixture to get NodeNorm/NameRes URLs from targets.ini
- Before writing a `requests` call and its checks, look in `src/babel_validation/services/service_checks.py`:
  `get_status()`, `get_normalized_node()` and `assert_x_translator()` already check the response's
  shape and escape what the service returned, and `get_status()` is cached per target
- For Google Sheet-based tests, parametrize with `gsheet.test_rows()` and use the `test_category` fixture for category filtering
- Use `pytest.mark.xfail(strict=True)` for known failures (strict=True means unexpected passes also fail)
- When a known failure is one check inside a test that also makes requests and checks shapes, give
  the xfail a narrow `raises=`: an `AssertionError` subclass raised only by that check, as
  `KnownElasticsearchDiscrepancy` does in `tests/nodenorm/test_nodenorm_endpoints.py`. A bare strict
  xfail — or `raises=AssertionError` — also absorbs a deployment that is down, a body that isn't
  JSON and every earlier assertion, so a new breakage reads as the old one. Raise it only on the
  bug's own signature, and use a plain assert for anything else that check could catch: only
  lower-cased `biolink:` classes, only an object keyed `"0"`..`"n-1"`, and a 500 only while the
  rest of the deployment still answers. "Not a list" or "any 500" would absorb an unrelated
  regression or an outage just the same. Don't swap the marker for
  an imperative `pytest.xfail()` plus `pytest.fail()` on a pass: that message starts with
  `Failed: `, so `generate_report.py` counts it as failed rather than xpassed
- Checks that an endpoint's *response shape* matches what NodeNorm's OpenAPI document and its Redis
  implementation promise go in `tests/nodenorm/test_nodenorm_endpoints.py`, which runs against every
  target; per-CURIE data regressions go in `by_issue/`
- **`tests/nodenorm/by_issue/` holds tests written for one particular bug**, each tied to the
  GitHub issue(s) that describe it, whoever or whatever wrote them. A test there catches the bug
  returning and shows when the specific problem in its issue has been fixed. If the bug turns
  out to be broader than its issue, the general check goes elsewhere in `tests/` (or into the
  GitHub issue tests); the per-issue test stays here.
- **A test whose expectations are only true from one Babel release on** (a compendium that
  did not exist before it, a clique it rearranged) calls
  `require_babel_release(target_info, "2026jul22")` from
  `src/babel_validation/services/service_checks.py` first. It
  skips targets serving an older release (prod and test were on 2025sep1 in 2026-11). Without
  it the test fails there for the wrong reason, and a strict xfail turns into an XPASS failure
  on an ES deployment that is simply one release behind. A target whose `/status` fails or
  reports no well-formed `babel_version` *fails* rather than skips: skipping would turn a
  broken `/status` into a green run that tested nothing.
- **Don't pin clique sizes or identifier counts in a regression test.** Assert the property the
  bug broke (no duplicates, no HTTP 500, not null) instead. `test_issue_11` once asserted the 17/32
  identifiers from its issue, which were one Babel release's cliques, and failed on every target
  running the next release with nothing actually wrong.
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
- **Don't assert on `caplog.text` for anything about control characters**: it does not carry
  them through, so such a test passes whatever the code does. Read `caplog.records` and
  `getMessage()` instead.
- Import shared classes from `src.babel_validation.*` (e.g. `from src.babel_validation.services.nodenorm import CachedNodeNorm`)
