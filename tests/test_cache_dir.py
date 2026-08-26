"""The cache directory must be private to the user, not the shared temp directory."""

import stat
import tempfile
from pathlib import Path

import pytest

from src.babel_validation.core import cache_dir
from tests.conftest import unlink_if_exists
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


def test_unlink_if_exists_refuses_paths_outside_the_cache(tmp_path):
    """It runs from pytest_configure and deletes whatever it is handed, so the containment
    check is what stops a later caller turning a cache sweep into a real delete."""
    precious = tmp_path / "precious.txt"
    precious.write_text("do not delete me")

    with pytest.raises(ValueError, match="Refusing to delete"):
        unlink_if_exists(precious)
    assert precious.read_text() == "do not delete me"


def test_unlink_if_exists_deletes_inside_the_cache():
    doomed = cache_dir() / "unit-test-scratch.json"
    doomed.write_text("{}")
    unlink_if_exists(doomed)
    assert not doomed.exists()
    unlink_if_exists(doomed)  # missing file is fine


def test_unlink_if_exists_survives_a_directory_in_the_way():
    """A directory where a cache file belongs must not fail the run before it starts."""
    blocker = cache_dir() / "unit-test-scratch-dir.csv"
    blocker.mkdir(exist_ok=True)
    try:
        unlink_if_exists(blocker)          # warns, does not raise
        assert blocker.is_dir()
    finally:
        blocker.rmdir()
