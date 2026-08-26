"""The cache directory must be private to the user, not the shared temp directory."""

import stat
import tempfile
from pathlib import Path

import pytest

from src.babel_validation.core import cache_dir
from tests._pytest_helpers import GITHUB_ISSUES_CACHE_FILE

pytestmark = pytest.mark.unit


def test_cache_dir_is_not_world_writable_temp(monkeypatch, tmp_path):
    """A fixed name in the shared temp directory lets any local user pre-create the file as
    a symlink, or rewrite its contents. The GitHub issue cache holds IDs a later run fetches
    and executes assertions from, so writing it is close to choosing what the run tests."""
    monkeypatch.setenv("BABEL_VALIDATION_CACHE_DIR", str(tmp_path / "cache"))
    path = cache_dir()

    assert path.is_dir()
    assert Path(tempfile.gettempdir()) not in path.parents
    # Owner-only: no group or other permissions at all.
    assert not stat.S_IMODE(path.stat().st_mode) & (stat.S_IRWXG | stat.S_IRWXO)


def test_cache_files_live_in_the_cache_dir():
    assert GITHUB_ISSUES_CACHE_FILE.parent == cache_dir()
