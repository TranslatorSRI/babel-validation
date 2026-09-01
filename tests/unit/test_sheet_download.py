"""Every Google Sheet download goes through one cached, locked helper.

Two things are pinned here. The cache is what keeps an xdist run to a single
request: pytest_generate_tests runs in every worker, so an uncached download
became one request per worker, and any one of them failing or differing made
that worker collect a different set of tests, which aborts the whole run with
"Different tests were collected between gw0 and gwN".

The second is that a failed download must not name the URL it failed on. The
sheet ID is the capability that grants access to an unauthenticated CSV export,
and dashboard.yaml runs pytest on a public repository.
"""

import csv
import io

import pytest
import requests

from src.babel_validation.sources.google_sheets import fetch_sheet_csv
from src.babel_validation.sources.google_sheets.blocklist import (
    load_blocklist_from_gsheet,
)

pytestmark = pytest.mark.unit

# Well-formed enough for resolve_sheet_id, and not anyone's real sheet.
FAKE_SHEET_ID = "0123456789abcdefghijABCDEFGHIJ"


def _blocklist_csv():
    """One blocked row, written with the csv module: several of the real column
    names contain commas or quotes, so a hand-written literal gets them wrong."""
    columns = [
        "Blocked?",
        "Status (Feb 21, 2024)",
        "Blocklist issue",
        'Block for "treats" only?',
        "Submitter",
        "Comment (optional)",
        "String (optional)",
        "CURIE (optional)",
    ]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerow(["y", "done", "1", "n", "someone", "", "dwarf", "MONDO:0000001"])
    return out.getvalue()


FAKE_CSV = _blocklist_csv()


class FakeResponse:
    def __init__(self, text="", status_code=200, reason="OK"):
        self.text = text
        self.status_code = status_code
        self.reason = reason

    def raise_for_status(self):
        if self.status_code >= 400:
            # The real message embeds the URL; that is the whole point of the test.
            raise requests.HTTPError(
                f"{self.status_code} Client Error: {self.reason} for url: "
                f"https://docs.google.com/spreadsheets/d/{FAKE_SHEET_ID}/gviz/tq",
                response=self,
            )


def _printed_chain(exc):
    """The messages a traceback would show: __cause__ always, __context__ only
    when it has not been suppressed by `raise ... from None`."""
    while exc is not None:
        yield str(exc)
        if exc.__cause__ is not None:
            exc = exc.__cause__
        elif not exc.__suppress_context__:
            exc = exc.__context__
        else:
            return


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Point cache_dir() at a scratch directory, and hand back the .env-loaded flag."""
    monkeypatch.setenv("BABEL_VALIDATION_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("BABEL_VALIDATION_SHEET_ID", FAKE_SHEET_ID)
    monkeypatch.setenv("BABEL_VALIDATION_BLOCKLIST_SHEET_ID", FAKE_SHEET_ID)
    return tmp_path


def test_repeated_downloads_hit_the_network_once(cache, monkeypatch):
    """The second caller — in an xdist run, another worker — reads the cache file."""
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return FakeResponse(FAKE_CSV)

    monkeypatch.setattr(requests, "get", fake_get)

    first = fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests")
    second = fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests")

    assert first == second == FAKE_CSV
    assert len(calls) == 1


def test_the_blocklist_is_cached_too(cache, monkeypatch):
    """The regression this file exists for: the blocklist used to fetch every time."""
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return FakeResponse(FAKE_CSV)

    monkeypatch.setattr(requests, "get", fake_get)

    assert len(load_blocklist_from_gsheet()) == 1
    assert len(load_blocklist_from_gsheet()) == 1
    assert len(calls) == 1


def test_two_tabs_do_not_share_a_cache_file(cache, monkeypatch):
    responses = {"Tests": "a,b\n1,2\n", "Other": "c,d\n3,4\n"}

    def fake_get(url, timeout=None):
        tab = url.rsplit("sheet=", 1)[1]
        return FakeResponse(responses[tab])

    monkeypatch.setattr(requests, "get", fake_get)

    assert fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests") == responses["Tests"]
    assert fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Other") == responses["Other"]


def test_a_stale_cache_is_refetched(cache, monkeypatch):
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return FakeResponse(FAKE_CSV)

    monkeypatch.setattr(requests, "get", fake_get)

    fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests")
    fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests", cache_ttl_seconds=0)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            lambda url, timeout=None: FakeResponse("", 429, "Too Many Requests"),
            id="http-error",
        ),
        pytest.param(
            lambda url, timeout=None: (_ for _ in ()).throw(
                requests.ConnectTimeout(
                    f"Connection to docs.google.com timed out: {url}"
                )
            ),
            id="connect-timeout",
        ),
    ],
)
def test_a_failed_download_never_names_the_sheet(cache, monkeypatch, failure):
    monkeypatch.setattr(requests, "get", failure)

    with pytest.raises(RuntimeError) as excinfo:
        fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests")

    # Not just str(excinfo.value): pytest prints an exception chain in full, so a
    # context that is merely attached would publish the original message — URL and
    # all — anyway. `raise ... from None` is what stops that, and this walks the
    # chain the same way the traceback module does, to prove it.
    rendered = "\n".join(_printed_chain(excinfo.value))
    assert FAKE_SHEET_ID not in rendered
    assert "docs.google.com" not in rendered
    # It still has to say something useful about what went wrong.
    assert "BABEL_VALIDATION_SHEET_ID" in str(excinfo.value)


def test_a_failed_download_is_not_cached(cache, monkeypatch):
    """A run that failed to download must not leave a poisoned cache behind."""
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, timeout=None: FakeResponse("", 503, "Service Unavailable"),
    )
    with pytest.raises(RuntimeError):
        fetch_sheet_csv("BABEL_VALIDATION_SHEET_ID", "Tests")

    assert list((cache / "cache").glob("gsheet_*.csv")) == []
