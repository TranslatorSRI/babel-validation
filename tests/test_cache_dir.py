"""The cache directory must be private to the user, not the shared temp directory."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

import src.babel_validation.core as core
from src.babel_validation.core import cache_dir
from tests.conftest import unlink_if_exists
from tests._pytest_helpers import GITHUB_ISSUES_CACHE_FILE

pytestmark = pytest.mark.unit


def test_default_cache_dir_is_not_in_the_shared_temp_dir(monkeypatch):
    """A fixed name in the shared temp directory lets any local user pre-create the file as a
    symlink, or rewrite its contents. The GitHub issue cache holds IDs a later run fetches and
    executes assertions from, so writing it is close to choosing what the run tests.

    Asserted against the *default* location, with the override cleared: pointing the override at
    a tmp_path and then asserting the result is not under the temp directory contradicts itself,
    and only looked like it passed because pytest resolves tmp_path to /private/var on macOS
    while gettempdir() reports /var.
    """
    monkeypatch.delenv("BABEL_VALIDATION_CACHE_DIR", raising=False)
    path = cache_dir()

    assert Path(tempfile.gettempdir()) not in path.parents
    assert Path.home() in path.parents


def test_cache_dir_loads_dotenv_itself(monkeypatch, tmp_path):
    """cache_dir() must not depend on someone else having loaded .env first.

    It used to read os.environ directly, so the answer changed mid-process:
    tests/conftest.py asks at import time, before anything has called
    resolve_sheet_id() (the only other .env reader), and got the default; the sheet
    downloads ask afterwards and got BABEL_VALIDATION_CACHE_DIR's value. The
    start-of-run gsheet_*.csv sweep was therefore globbing an empty directory, and
    unlink_if_exists()'s containment check compares against a cache_dir() that must
    not move under it.
    """
    target = tmp_path / "from-dotenv"

    def fake_load_dotenv(*args, **kwargs):
        # monkeypatch.setenv, not os.environ[...]: where there is no .env at all
        # (CI), the delenv below has no previous value to restore, so a raw write
        # here outlives the test and poisons whatever runs next.
        monkeypatch.setenv("BABEL_VALIDATION_CACHE_DIR", str(target))

    monkeypatch.delenv("BABEL_VALIDATION_CACHE_DIR", raising=False)
    monkeypatch.setattr(core, "_dotenv_loaded", False)
    monkeypatch.setattr(core.dotenv, "load_dotenv", fake_load_dotenv)

    assert cache_dir() == target


def test_a_deleted_override_stays_deleted(monkeypatch):
    """.env is loaded once per process, not on every call.

    load_dotenv() will not override a key already in os.environ, but it does re-set
    one that has been deleted — so reloading on each call would make it impossible
    to unset the override, here or anywhere else. (By the time any test runs, the
    import of tests/conftest.py has already triggered the one load.)
    """
    monkeypatch.delenv("BABEL_VALIDATION_CACHE_DIR", raising=False)
    default = Path.home() / ".cache" / "babel-validation"

    assert cache_dir() == default
    assert cache_dir() == default


def test_cache_dir_is_created_private(monkeypatch, tmp_path):
    """Owner-only: no group or other permissions at all."""
    monkeypatch.setenv("BABEL_VALIDATION_CACHE_DIR", str(tmp_path / "cache"))
    path = cache_dir()

    assert path.is_dir()
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
        unlink_if_exists(blocker)  # warns, does not raise
        assert blocker.is_dir()
    finally:
        blocker.rmdir()


def test_unset_home_still_resolves(monkeypatch):
    """Path.home() falls back to the pwd database, so an unset HOME is not by itself a problem —
    pinned because it is the reason cache_dir() does not need to special-case it."""
    monkeypatch.delenv("BABEL_VALIDATION_CACHE_DIR", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    assert cache_dir().is_dir()


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores the permission bits this relies on"
)
def test_unwritable_location_names_the_override(monkeypatch, tmp_path):
    """A locked-down runner or container is the realistic case. The bare PermissionError names a
    path but not the escape hatch, so the error has to mention the environment variable.
    """
    readonly = tmp_path / "readonly"
    readonly.mkdir(mode=0o500)
    monkeypatch.setenv("BABEL_VALIDATION_CACHE_DIR", str(readonly / "cache"))

    with pytest.raises(RuntimeError, match="BABEL_VALIDATION_CACHE_DIR"):
        cache_dir()
