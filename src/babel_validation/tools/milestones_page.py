"""
Generate a single HTML page listing every open milestone across the Babel repositories.

Why this exists
---------------
Milestones are the commitment mechanism for this family of projects: when an issue
needs to be dealt with by some (soft) deadline, it goes into a milestone. That works
well per-repository, but milestones cannot span repositories, so "what have I actually
committed to?" means checking five separate milestone pages across two organizations.

This tool merges them into one chronological page. The page is *derived* — it is
regenerated from the milestones themselves, so unlike a project board it cannot drift
out of sync with them. Published to GitHub Pages, it doubles as the answer to
"when will you get to my bug?" for people outside the project.

Deliberately reads milestones and issues only. Pulling fields off a GitHub Project
would need a token with `project` scope — a PAT held as an organization secret in
both TranslatorSRI and NCATSTranslator — whereas every repository below is public,
so a workflow's built-in GITHUB_TOKEN is enough. Priority and component therefore
live in labels, not project fields.
"""

import argparse
import datetime
import html
import logging
import os

from github import Github, Auth

_logger = logging.getLogger(__name__)

# The Babel Tools family. Two organizations, which is exactly why the per-repo
# milestone pages don't add up to a usable view.
DEFAULT_REPOSITORIES = [
    "NCATSTranslator/Babel",
    "NCATSTranslator/NodeNormalization",
    "NCATSTranslator/NameResolution",
    "TranslatorSRI/babel-validation",
    "TranslatorSRI/babel-explorer",
]

# Milestones used as priority buckets rather than release trains. They have no due
# date and never close, so they'd sit at the bottom of the page forever. Listed so
# the page can group them separately instead of pretending they're deadlines.
BUCKET_TITLES = {"immediate", "needed soon", "needed later", "not urgent"}


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
    for repo_name in repositories:
        repo = github.get_repo(repo_name)
        for milestone in repo.get_milestones(state="open"):
            issues = list(repo.get_issues(milestone=milestone, state="open"))
            _logger.info("%s: milestone %r has %d open issues", repo_name, milestone.title, len(issues))
            collected.append((repo_name, milestone, issues))
    collected.sort(key=lambda entry: sort_key(entry[1]))
    return collected


def _issue_html(repo_name: str, issue) -> str:
    labels = "".join(f'<span class="label">{html.escape(label.name)}</span>' for label in issue.labels)
    assignee = f' <span class="assignee">@{html.escape(issue.assignees[0].login)}</span>' if issue.assignees else ""
    return (
        f'<li><a href="{issue.html_url}">{repo_name.split("/")[1]}#{issue.number}</a> '
        f"{html.escape(issue.title)}{assignee} {labels}</li>"
    )


def _milestone_html(repo_name: str, milestone, issues: list, today: datetime.date) -> str:
    if milestone.due_on:
        due = milestone.due_on.date()
        overdue = ' <span class="overdue">PAST DUE</span>' if due < today else ""
        due_html = f"due {due.isoformat()}{overdue}"
    else:
        due_html = "no due date"

    total = milestone.open_issues + milestone.closed_issues
    # An empty milestone is a cleanup candidate, so say so rather than showing a blank list.
    issue_items = "\n".join(_issue_html(repo_name, issue) for issue in issues) or "<li><em>No open issues.</em></li>"
    return f"""<section>
<h2><a href="{milestone.html_url}">{html.escape(milestone.title)}</a></h2>
<p class="meta">{html.escape(repo_name)} &middot; {due_html} &middot;
{milestone.open_issues} open / {total} total</p>
<ul>
{issue_items}
</ul>
</section>"""


# ponytail: hand-rolled HTML in an f-string. Fine at this size; switch to a template
# engine if the page grows past a couple of sections.
def render(collected: list, generated_at: datetime.datetime) -> str:
    today = generated_at.date()
    releases = [entry for entry in collected if not is_bucket(entry[1])]
    buckets = [entry for entry in collected if is_bucket(entry[1])]

    body = "\n".join(_milestone_html(repo, milestone, issues, today) for repo, milestone, issues in releases)
    if buckets:
        body += '\n<h1 class="buckets">Priority buckets (not deadlines)</h1>\n'
        body += "\n".join(_milestone_html(repo, milestone, issues, today) for repo, milestone, issues in buckets)

    open_count = sum(len(issues) for _, _, issues in collected)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Babel Milestones</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; line-height: 1.5; }}
h2 {{ margin-bottom: 0; }}
.meta {{ color: #666; margin-top: .2em; font-size: .9em; }}
.overdue {{ color: #b00; font-weight: bold; }}
.label {{ background: #eee; border-radius: 1em; padding: 0 .6em; font-size: .8em; margin-left: .3em; }}
.assignee {{ color: #666; font-size: .9em; }}
.buckets {{ margin-top: 3em; border-top: 2px solid #ccc; padding-top: 1em; }}
li {{ margin: .3em 0; }}
</style>
</head>
<body>
<h1>Babel Milestones</h1>
<p class="meta">{len(collected)} open milestones &middot; {open_count} open issues &middot;
generated {generated_at.strftime("%Y-%m-%d %H:%M UTC")}</p>
{body}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="milestones.html", help="File to write the HTML page to.")
    parser.add_argument(
        "--repository", action="append", dest="repositories", help="Repository to include (repeatable)."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("No GITHUB_TOKEN in the environment.")

    github = Github(auth=Auth.Token(token))
    collected = collect(github, args.repositories or DEFAULT_REPOSITORIES)
    generated_at = datetime.datetime.now(datetime.timezone.utc)

    with open(args.output, "w") as f:
        f.write(render(collected, generated_at))
    _logger.info("Wrote %d milestones to %s", len(collected), args.output)


if __name__ == "__main__":
    main()
