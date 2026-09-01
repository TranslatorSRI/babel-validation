# Google Sheet IDs are deliberately not checked in: for an unauthenticated CSV
# export the ID is the capability that grants access, so each sheet's ID lives
# in an environment variable (via .env locally, a repository secret in GitHub
# Actions) and must never appear in the code, the Git history, or anything we
# publish.
import hashlib
import os
import re
import time
import urllib.parse

import dotenv
import requests
from filelock import FileLock

from ...core import cache_dir

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


def fetch_sheet_csv(
    env_var,
    sheet_name,
    sheet_id=None,
    cache_ttl_seconds: int = 3600,
    timeout: int = 30,
) -> str:
    """
    Download one tab of a Google Sheet as CSV and return the text.

    The download is cached in cache_dir() and guarded by a FileLock, so a whole
    xdist run costs one request no matter how many workers ask: the first worker
    to take the lock fetches, the rest read the file it wrote. pytest deletes the
    cache at the start of every run (see tests/conftest.py), so the TTL mainly
    protects other consumers (e.g. csv-to-babeltests) from reading stale data
    forever.

    :param env_var: The environment variable holding this sheet's ID.
    :param sheet_name: The name of the tab to export.
    :param sheet_id: An explicit sheet ID, overriding the environment variable.
    :param cache_ttl_seconds: How long a cached download stays valid.
    :param timeout: Per-request timeout, in seconds.
    :return: The CSV text of that tab.
    """
    sheet_id = resolve_sheet_id(env_var, sheet_id)

    # The tab is part of the identity of the download: two tabs of one sheet are
    # two different CSVs and must not share a cache file.
    key = hashlib.md5(f"{sheet_id}\0{sheet_name}".encode()).hexdigest()
    cache_file = cache_dir() / f"gsheet_{key}.csv"
    lock_file = cache_file.with_suffix(".lock")

    with FileLock(lock_file):
        if (
            cache_file.exists()
            and time.time() - cache_file.stat().st_mtime < cache_ttl_seconds
        ):
            return cache_file.read_text(encoding="utf-8")

        csv_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
            f"?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}"
        )
        response = requests.get(csv_url, timeout=timeout)
        response.raise_for_status()
        csv_content = response.text
        cache_file.write_text(csv_content, encoding="utf-8")

    return csv_content
