# Google Sheet IDs are deliberately not checked in: for an unauthenticated CSV
# export the ID is the capability that grants access, so each sheet's ID lives
# in an environment variable (via .env locally, a repository secret in GitHub
# Actions) and must never appear in the code, the Git history, or anything we
# publish.
import os
import re

import dotenv

_SHEET_ID_RE = re.compile(r"[A-Za-z0-9_-]{20,}")


def resolve_sheet_id(env_var, sheet_id=None):
    """
    Return a validated Google Sheet ID: the one passed in, or the value of the
    named environment variable (loading .env first). A missing or implausible
    value fails loudly — the ID goes into a URL path, and the format check also
    catches quoting mistakes in .env.
    """
    if sheet_id is None:
        dotenv.load_dotenv()
        sheet_id = os.environ.get(env_var)
        if not sheet_id:
            raise RuntimeError(
                f"No Google Sheet ID: set {env_var} (e.g. in .env). "
                "Ask a maintainer for the ID."
            )
    if not _SHEET_ID_RE.fullmatch(sheet_id):
        raise RuntimeError(f"{env_var} does not look like a Google Sheet ID.")
    return sheet_id
