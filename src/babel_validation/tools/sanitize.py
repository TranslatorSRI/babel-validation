#
# sanitize.py - the primitives every generator uses on its way to a public file.
#
# Both tools in this package publish to the same public website, and both read
# text nobody reviewed: pytest messages carrying Google Sheet cells and GitHub
# issue bodies in generate_report.py, milestone and issue titles in
# generate_milestones.py. The rules are identical either way, so they live here
# rather than being written twice and drifting apart.
#
# generate_report.py re-exports these, so `from ... generate_report import
# sanitize` keeps working — the module docstring there still describes it as the
# choke point for report.json, and it is; this file just holds the tools.
#

import re

MAX_MESSAGE_CHARS = 500


def sanitize(text, max_chars=MAX_MESSAGE_CHARS):
    """
    Truncate untrusted text and escape every non-printable character (ANSI
    escapes, C0/C1 controls, bidi overrides, zero-width characters) the way
    repr() would, keeping newlines and tabs readable. Escaping rather than
    stripping keeps hostile content visible instead of silently vanishing.
    """
    if text is None:
        return None
    text = str(text)
    if len(text) > max_chars:
        text = text[:max_chars] + "…[truncated]"
    return "".join(
        ch if ch.isprintable() or ch in "\n\t" else repr(ch)[1:-1] for ch in text
    )


# Issue ids must look like org/repo#N *and* be in the checked-in allowlist
# before we build a github.com link from them.
ISSUE_ID_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)$")


def validate_issue_id(issue_id, allowlist):
    """Return the validated 'org/repo#N' or None."""
    match = ISSUE_ID_RE.match(issue_id or "")
    if not match:
        return None
    if match.group(1).lower() not in allowlist:
        return None
    return issue_id


def validate_source_url(source_url, allowlist):
    """
    Return source_url only if it is a GitHub URL within an allowlisted
    org/repo; otherwise None. SourceURL is free text from the Google Sheet.
    """
    if not source_url or not source_url.startswith("https://github.com/"):
        return None
    parts = source_url[len("https://github.com/") :].split("/")
    if len(parts) < 2:
        return None
    if f"{parts[0]}/{parts[1]}".lower() not in allowlist:
        return None
    return source_url
