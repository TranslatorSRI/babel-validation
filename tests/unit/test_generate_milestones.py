"""Unit tests for the milestones data generator. No network: every milestone and
issue is a SimpleNamespace, and the hostile inputs are inline."""

import datetime
from types import SimpleNamespace

import pytest

from src.babel_validation.tools.generate_milestones import (
    build_milestones,
    is_bucket,
    sort_key,
)

# These build milestones out of SimpleNamespace and touch no network, and CI runs
# `pytest -m unit`: without this marker all of them are deselected and never run
# there. That is not hypothetical — this file's six predecessors never once ran.
pytestmark = pytest.mark.unit

ALLOWLIST = ["ncatstranslator/babel", "translatorsri/babel-validation"]


def _utc(year, month, day):
    return datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)


def _milestone(title, due_on=None, number=1, open_issues=0, closed_issues=0):
    return SimpleNamespace(
        title=title,
        due_on=due_on,
        number=number,
        open_issues=open_issues,
        closed_issues=closed_issues,
    )


def _issue(number, title, labels=(), assignees=()):
    return SimpleNamespace(
        number=number,
        title=title,
        labels=[SimpleNamespace(name=name) for name in labels],
        assignees=[SimpleNamespace(login=login) for login in assignees],
    )


def _build(entries, generated_at=None):
    return build_milestones(entries, ALLOWLIST, generated_at or _utc(2026, 8, 20))


class TestOrdering:
    def test_undated_milestones_sort_last(self):
        """A milestone with no due date belongs after every real deadline, not before it."""
        milestones = [
            _milestone("no deadline"),
            _milestone("later", _utc(2026, 9, 1)),
            _milestone("sooner", _utc(2026, 8, 1)),
        ]
        assert [m.title for m in sorted(milestones, key=sort_key)] == [
            "sooner",
            "later",
            "no deadline",
        ]

    def test_bucket_detection(self):
        """Undated legacy priority buckets are buckets; anything with a due date is a release."""
        assert is_bucket(_milestone("Needed soon"))
        assert is_bucket(_milestone("immediate"))  # matched case-insensitively
        assert not is_bucket(_milestone("Babel v1.19", _utc(2026, 8, 19)))
        assert not is_bucket(_milestone("Some other undated milestone"))

    def test_buckets_are_flagged_so_the_page_can_separate_them(self):
        """The split lives in the data, not in the component: one flag per milestone."""
        data = _build(
            [
                (
                    "NCATSTranslator/Babel",
                    _milestone("Babel v1.19", _utc(2026, 9, 1)),
                    [],
                ),
                ("NCATSTranslator/Babel", _milestone("Needed soon"), []),
            ]
        )
        assert [m["bucket"] for m in data["milestones"]] == [False, True]

    def test_past_due_is_true_only_when_overdue(self):
        data = _build(
            [
                ("NCATSTranslator/Babel", _milestone("overdue", _utc(2026, 7, 20)), []),
                (
                    "NCATSTranslator/Babel",
                    _milestone("upcoming", _utc(2026, 9, 20)),
                    [],
                ),
                ("NCATSTranslator/Babel", _milestone("undated"), []),
            ]
        )
        assert [m["past_due"] for m in data["milestones"]] == [True, False, False]
        assert data["milestones"][2]["due_on"] is None


class TestUntrustedText:
    def test_titles_are_escaped_not_passed_through(self):
        """Titles are arbitrary user text and land on a public page."""
        issues = [_issue(7, "Handle \x1b[2J and ‮ overrides", labels=["a\x00b"])]
        milestone = _milestone("Babel \x07v1.19", _utc(2026, 9, 1), open_issues=1)
        data = _build([("NCATSTranslator/Babel", milestone, issues)])

        rendered = data["milestones"][0]
        assert "\x1b" not in rendered["issues"][0]["title"]
        assert "‮" not in rendered["issues"][0]["title"]
        assert "\x07" not in rendered["title"]
        assert "\x00" not in rendered["issues"][0]["labels"][0]
        # Escaped, not stripped: hostile content stays visible.
        assert "\\x1b" in rendered["issues"][0]["title"]

    def test_a_long_title_is_truncated(self):
        issues = [_issue(7, "x" * 5000)]
        data = _build(
            [("NCATSTranslator/Babel", _milestone("m", _utc(2026, 9, 1)), issues)]
        )
        assert len(data["milestones"][0]["issues"][0]["title"]) < 300

    def test_an_issue_outside_the_allowlist_gets_no_id(self):
        """No id means the page has nothing to build a link from, which is the point."""
        data = _build(
            [("Someone/Elsewhere", _milestone("m", _utc(2026, 9, 1)), [_issue(7, "t")])]
        )
        entry = data["milestones"][0]["issues"][0]
        assert "issue" not in entry
        assert entry["title"] == "t"

    def test_an_allowlisted_issue_gets_an_org_repo_hash_id(self):
        data = _build(
            [
                (
                    "NCATSTranslator/Babel",
                    _milestone("m", _utc(2026, 9, 1)),
                    [_issue(7, "t")],
                )
            ]
        )
        assert data["milestones"][0]["issues"][0]["issue"] == "NCATSTranslator/Babel#7"


class TestShape:
    def test_an_empty_milestone_still_appears(self):
        """An empty milestone is a cleanup candidate: it has to be visible to be cleaned up."""
        data = _build(
            [
                (
                    "NCATSTranslator/Babel",
                    _milestone("Hackathon 2026", _utc(2026, 6, 2)),
                    [],
                )
            ]
        )
        (milestone,) = data["milestones"]
        assert milestone["issues"] == []
        assert milestone["open_issues"] == 0

    def test_optional_issue_fields_are_omitted_when_absent(self):
        issues = [_issue(7, "t"), _issue(8, "u", labels=["bug"], assignees=["someone"])]
        data = _build(
            [("NCATSTranslator/Babel", _milestone("m", _utc(2026, 9, 1)), issues)]
        )
        bare, full = data["milestones"][0]["issues"]
        assert "assignee" not in bare and "labels" not in bare
        assert full["assignee"] == "someone" and full["labels"] == ["bug"]

    def test_the_run_stamp_is_present(self):
        data = _build([], generated_at=_utc(2026, 8, 20))
        assert data["generated_at"].startswith("2026-08-20")
        assert set(data["run"]) == {"github_run_id", "git_sha"}
