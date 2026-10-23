"""
Build the milestones data file behind the dashboard's /milestones/ page.

Why this exists
---------------
Milestones are the commitment mechanism for this family of projects: when an issue
needs to be dealt with by some (soft) deadline, it goes into a milestone. That works
well per-repository, but milestones cannot span repositories, so "what have I actually
committed to?" means checking five separate milestone pages across two organizations.

This tool merges them into one chronological list. The page is *derived* — it is
regenerated from the milestones themselves, so unlike a project board it cannot drift
out of sync with them. Published on GitHub Pages, it doubles as the answer to
"when will you get to my bug?" for people outside the project.

Deliberately reads milestones and issues only. Pulling fields off a GitHub Project
would need a token with `project` scope — a PAT held as an organization secret in
both TranslatorSRI and NCATSTranslator — whereas every repository in targets.ini's
`Repositories` list is public, so a workflow's built-in GITHUB_TOKEN is enough.
Priority and component therefore live in labels, not project fields.

Untrusted input
---------------
Milestone titles, issue titles, label names and assignee logins are written by anyone
with a GitHub account, and this writes them to a public website. So this module is a
choke point in the same sense generate_report.py is: every string goes through
sanitize(), issue ids are emitted only as allowlisted `org/repo#N` (never as a URL —
the page rebuilds the link from the validated parts), and issue *bodies* are never
read at all.
"""

import argparse
import datetime
import json
import logging
import os
from pathlib import Path

from github import Github, Auth

from src.babel_validation.tools.generate_report import read_repositories, read_targets
from src.babel_validation.tools.sanitize import sanitize, validate_issue_id

_logger = logging.getLogger(__name__)

# Milestones used as priority buckets rather than release trains. They have no due
# date and never close, so they'd sit at the bottom of the page forever. Listed so
# the page can group them separately instead of pretending they're deadlines.
BUCKET_TITLES = {"immediate", "needed soon", "needed later", "not urgent"}

# Titles and label names are short by nature; a 500-character one is someone
# testing what happens, not a milestone. Kept well under sanitize()'s default so a
# hostile title cannot push the page's layout around.
MAX_TITLE_CHARS = 200
MAX_LABEL_CHARS = 60


def sort_key(milestone):
    """Order milestones by due date, undated ones last.

    datetime.date.max stands in for "no due date" so undated milestones sort after
    every real deadline instead of raising on a None comparison.
    """
    due = milestone.due_on
    return (due.date() if due else datetime.date.max, milestone.title)


def is_bucket(milestone) -> bool:
    """True for the legacy priority-bucket milestones (see BUCKET_TITLES)."""
    return milestone.due_on is None and milestone.title.lower() in BUCKET_TITLES


def collect(github: Github, repositories: list[str]) -> list[tuple[str, object, list]]:
    """Return (repo_name, milestone, open_issues) for every open milestone, in page order."""
    collected = []
    calls = 0
    for repo_name in repositories:
        repo = github.get_repo(repo_name)
        calls += 1
        for milestone in repo.get_milestones(state="open"):
            issues = list(repo.get_issues(milestone=milestone, state="open"))
            calls += 1
            _logger.info(
                "%s: milestone %r has %d open issues",
                repo_name,
                milestone.title,
                len(issues),
            )
            collected.append((repo_name, milestone, issues))
    collected.sort(key=lambda entry: sort_key(entry[1]))
    # Logged because it is the number that grows: one call per repository plus one
    # per open milestone, against 5000/hour for the built-in token.
    _logger.info("Collected %d milestones in ~%d API calls", len(collected), calls)
    return collected


def _issue_entry(repo_name, issue, allowlist):
    """One issue, reduced to what the page renders and nothing more."""
    entry = {"title": sanitize(issue.title, MAX_TITLE_CHARS)}
    # org/repo#N, and only when it passes the same allowlist check report.json
    # uses. The page turns this into a link; anything unvalidated has to render
    # as plain text instead, which is why the key is simply absent when it fails.
    issue_id = validate_issue_id(f"{repo_name}#{issue.number}", allowlist)
    if issue_id:
        entry["issue"] = issue_id
    if issue.assignees:
        entry["assignee"] = sanitize(issue.assignees[0].login, MAX_LABEL_CHARS)
    labels = [sanitize(label.name, MAX_LABEL_CHARS) for label in issue.labels]
    if labels:
        entry["labels"] = labels
    return entry


def build_milestones(collected, allowlist, generated_at):
    """Turn collect()'s output into the published milestones.json structure."""
    today = generated_at.date()
    milestones = []
    for repo_name, milestone, issues in collected:
        due = milestone.due_on.date() if milestone.due_on else None
        entry = {
            "repo": sanitize(repo_name, MAX_TITLE_CHARS),
            "title": sanitize(milestone.title, MAX_TITLE_CHARS),
            "number": milestone.number,
            "due_on": due.isoformat() if due else None,
            "past_due": bool(due and due < today),
            "bucket": is_bucket(milestone),
            "open_issues": milestone.open_issues,
            "closed_issues": milestone.closed_issues,
            "issues": [_issue_entry(repo_name, issue, allowlist) for issue in issues],
        }
        # The same validated org/repo#N shape the issues use, so the page can
        # build a milestone link from parts that passed the allowlist rather
        # than from the repo name as text. Absent when it fails, leaving the
        # title to render unlinked.
        milestone_id = validate_issue_id(f"{repo_name}#{milestone.number}", allowlist)
        if milestone_id:
            entry["milestone"] = milestone_id
        milestones.append(entry)
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "run": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "git_sha": os.environ.get("GITHUB_SHA"),
        },
        "milestones": milestones,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, help="File to write milestones.json to."
    )
    parser.add_argument(
        "--targets-ini",
        default="tests/targets.ini",
        help="targets.ini to read the repository list from.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("No GITHUB_TOKEN in the environment.")

    # One list, not two. targets.ini's `Repositories` is checked-in config and is
    # already exactly this family of repositories; keeping a second copy here is
    # how the workflow's target loop drifted from read_targets() once already. If
    # the two questions ever diverge — "whose assertions do we run" is not
    # inherently "whose milestones do we track" — add a MilestoneRepositories key
    # that falls back to this one, rather than a hardcoded list.
    _, allowlist, config = read_targets(args.targets_ini)
    repositories = read_repositories(config)

    github = Github(auth=Auth.Token(token))
    collected = collect(github, repositories)
    generated_at = datetime.datetime.now(datetime.timezone.utc)
    data = build_milestones(collected, allowlist, generated_at)

    # Created here rather than by the caller, as generate_report.py does with
    # --out-dir: the workflow writes into a directory that does not exist on a
    # fresh checkout, and so does anyone running this locally.
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        # allow_nan=False for the same reason generate_report.py sets it: a file
        # no browser can parse is worse than a run that failed.
        json.dump(data, f, separators=(",", ":"), allow_nan=False)
    _logger.info("Wrote %d milestones to %s", len(collected), args.output)


if __name__ == "__main__":
    main()
