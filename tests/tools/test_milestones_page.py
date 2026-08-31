"""Checks for the milestone-ordering logic in src.babel_validation.tools.milestones_page."""

import datetime
from types import SimpleNamespace

import pytest

from src.babel_validation.tools.milestones_page import is_bucket, render, sort_key

# These build milestones out of SimpleNamespace and touch no network, and CI runs
# `pytest -m unit`: without this marker all six are deselected and never run there.
pytestmark = pytest.mark.unit


def _milestone(title, due_on=None):
    return SimpleNamespace(title=title, due_on=due_on)


def _utc(year, month, day):
    return datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)


def test_undated_milestones_sort_last():
    """A milestone with no due date belongs after every real deadline, not before it."""
    milestones = [
        _milestone("no deadline"),
        _milestone("later", _utc(2026, 9, 1)),
        _milestone("sooner", _utc(2026, 8, 1)),
    ]
    assert [m.title for m in sorted(milestones, key=sort_key)] == ["sooner", "later", "no deadline"]


def test_bucket_detection():
    """Undated legacy priority buckets are buckets; anything with a due date is a release."""
    assert is_bucket(_milestone("Needed soon"))
    assert is_bucket(_milestone("immediate"))  # matched case-insensitively
    assert not is_bucket(_milestone("Babel v1.19", _utc(2026, 8, 19)))
    assert not is_bucket(_milestone("Some other undated milestone"))


def _issue(number, title, labels=(), assignees=()):
    return SimpleNamespace(
        number=number,
        title=title,
        html_url=f"https://github.com/NCATSTranslator/Babel/issues/{number}",
        labels=[SimpleNamespace(name=name) for name in labels],
        assignees=[SimpleNamespace(login=login) for login in assignees],
    )


def _full_milestone(title, due_on, open_issues, closed_issues):
    return SimpleNamespace(
        title=title,
        due_on=due_on,
        open_issues=open_issues,
        closed_issues=closed_issues,
        html_url="https://github.com/NCATSTranslator/Babel/milestone/1",
    )


def test_issue_titles_are_escaped():
    """Issue titles are arbitrary user text, so an unescaped < or & would break the page."""
    milestone = _full_milestone("Babel v1.19", _utc(2026, 9, 1), 1, 0)
    issues = [_issue(7, "Handle <script> & other markup in labels")]
    page = render([("NCATSTranslator/Babel", milestone, issues)], _utc(2026, 8, 20))
    assert "&lt;script&gt; &amp; other" in page
    assert "<script>" not in page


def test_past_due_is_flagged_only_when_overdue():
    generated_at = _utc(2026, 8, 20)
    overdue = _full_milestone("NodeNorm v2.5.0", _utc(2026, 7, 20), 1, 0)
    upcoming = _full_milestone("NodeNorm v2.6.0", _utc(2026, 9, 20), 1, 0)
    assert "PAST DUE" in render([("NCATSTranslator/Babel", overdue, [])], generated_at)
    assert "PAST DUE" not in render([("NCATSTranslator/Babel", upcoming, [])], generated_at)


def test_buckets_render_below_releases():
    """Undated buckets belong in their own section, after every real deadline."""
    release = _full_milestone("Babel v1.19", _utc(2026, 9, 1), 1, 0)
    bucket = _full_milestone("Needed soon", None, 1, 0)
    page = render(
        [("NCATSTranslator/Babel", release, []), ("NCATSTranslator/Babel", bucket, [])],
        _utc(2026, 8, 20),
    )
    assert page.index("Babel v1.19") < page.index("Priority buckets") < page.index("Needed soon")


def test_empty_milestone_says_so():
    """An empty milestone is a cleanup candidate, so it should read as empty, not blank."""
    milestone = _full_milestone("Translator June Hackathon 2026", _utc(2026, 6, 2), 0, 0)
    assert "No open issues." in render([("NCATSTranslator/Babel", milestone, [])], _utc(2026, 8, 20))
