"""Checks for the milestone-ordering logic in src.babel_validation.tools.milestones_page."""

import datetime
from types import SimpleNamespace

from src.babel_validation.tools.milestones_page import is_bucket, sort_key


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
