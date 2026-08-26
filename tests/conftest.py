#
# conftest.py - pytest configuration settings
#
import glob
import json
import logging
import os
import os.path
from pathlib import Path

import pytest
import configparser

from src.babel_validation.core import cache_dir
from tests._pytest_helpers import GITHUB_ISSUES_CACHE_FILE


def get_targets_ini_path(config):
    """
    Return the path to targets.ini. Because of some confusion over the root path, this checks both:
        - rootpath + '/targets.ini'
        - rootpath + '/tests/targets.ini'.

    :param config: PyTest configuration settings.
    :return: The filepath to targets.ini, or raises an exception if it can't be found.
    """
    config_path = os.path.join(config.rootpath, 'targets.ini')
    if not os.path.isfile(config_path):
        config_path_with_tests = os.path.join(config.rootpath, 'tests', 'targets.ini')
        if not os.path.isfile(config_path_with_tests):
            raise RuntimeError(f"Could not find targets.ini configuration file at either {config_path} or {config_path_with_tests}")
        return config_path_with_tests
    return config_path


def unlink_if_exists(path) -> None:
    """
    Delete `path` if it exists. `path` must be inside cache_dir().

    This function deletes whatever it is handed, and it runs from pytest_configure before
    anything else in the session. The containment check is not about today's two callers,
    which both build their paths from cache_dir(); it is so that a later one cannot quietly
    turn a cache sweep into a delete of something that matters.

    Note that os.unlink does not follow symlinks — it removes the link, not its target — so
    a planted symlink here would be deleted rather than followed. It was the *write* side
    that could be redirected, and moving the caches out of the shared temp directory is what
    closed that.

    :param path: The path to the file to delete. Must be within cache_dir().
    :return: None
    """
    path = Path(path)
    if cache_dir() not in path.parents:
        raise ValueError(f"Refusing to delete {path}, which is outside the cache directory {cache_dir()}")
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        # Something is in the way — a directory left where a cache file belongs, or a
        # permissions problem. A stale cache is not worth failing the whole run over.
        logging.getLogger(__name__).warning("Could not delete cached file %s: %s", path, e)


# Open file handle for --report-jsonl, or None. Controller-only: xdist workers
# forward their TestReports (including user_properties and wasxfail) to the
# controller, where pytest_runtest_logreport fires again, so only the controller
# needs to write.
_report_file = None


def pytest_configure(config):
    global _report_file
    report_path = config.getoption('--report-jsonl')
    if report_path and not os.environ.get('PYTEST_XDIST_WORKER'):
        _report_file = open(report_path, 'a', encoding='utf-8')

    # Delete the Google Sheet CSV cache at the start of each run so tests always
    # use a fresh download. Only the controller does this — xdist workers skip it
    # so they can share the cache file written by the controller.
    if not os.environ.get('PYTEST_XDIST_WORKER'):
        # Only the .csv files. Their .lock files are left alone for the same reason as the
        # issue cache's below — this used to unlink `<name>.lock` alongside each `<name>.csv`,
        # which is the hazard 48b1c44 removed for the issue lock and missed here.
        for f in glob.glob(os.path.join(cache_dir(), 'gsheet_*.csv')):
            unlink_if_exists(f)
        # Same for the GitHub issue ID cache. The matching .lock file is left
        # alone: deleting it out from under a concurrently running pytest would
        # let that run and this one hold two different inodes of "the" lock.
        unlink_if_exists(GITHUB_ISSUES_CACHE_FILE)


def pytest_runtest_logreport(report):
    """
    When --report-jsonl is set, write one JSON line per test phase: every 'call'
    report, plus setup/teardown reports that did not pass (setup skips and
    errors). Raw pytest facts only — classification into
    passed/failed/xfailed/xpassed/skipped/error happens in
    src.babel_validation.tools.generate_report, where it is unit-testable.

    longrepr may contain untrusted text (issue bodies, sheet cells, service
    responses); it is truncated here and repr-escaped by the report generator
    before it is displayed anywhere.
    """
    if _report_file is None:
        return
    if report.when != 'call' and report.outcome == 'passed':
        return
    # Prefer the one-line crash message ("AssertionError: ...") over the full
    # traceback with source and locals; skips have a (path, line, reason) tuple
    # longrepr with no reprcrash, for which str() is already the short form.
    msg = None
    if report.longrepr is not None:
        crash = getattr(report.longrepr, 'reprcrash', None)
        msg = crash.message if crash is not None else str(report.longrepr)
    record = {
        "id": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "wasxfail": hasattr(report, 'wasxfail'),
        "duration": round(report.duration, 3),
        "props": dict(report.user_properties or []),
        "msg": msg[:2000] if msg else None,
    }
    _report_file.write(json.dumps(record) + "\n")
    _report_file.flush()


def pytest_addoption(parser):
    # The target environment(s) to target.
    parser.addoption(
        '--target',
        default=[],
        action='append',  # You can specify multiple targets, e.g. `--target prod --target dev`
        help="The target to test. See targets.ini file for a list of targets."
    )
    # Categories to process.
    parser.addoption(
        '--category',
        default=[],
        action='append',
        help="The categories of tests to run."
    )
    parser.addoption(
        '--category-exclude',
        default=[],
        action='append',
        help="The categories of tests to exclude."
    )

    # Write one JSON line per test outcome, for the dashboard report generator.
    parser.addoption(
        '--report-jsonl',
        default=None,
        help="Append raw per-test outcome records (JSONL) to this file, for "
             "src.babel_validation.tools.generate_report."
    )

    # Only test particular GitHub issues.
    parser.addoption(
        '--issue',
        default=[],
        action='append',
        help="One or more GitHub issues to test. Should be specified as either 'organization/repo#110', 'repo#110' or '110'"
    )


def read_targets(config_path):
    cp = configparser.ConfigParser()
    cp.read(config_path, encoding='utf8')
    return cp


def get_target(config, target):
    config_path = get_targets_ini_path(config)
    targets = read_targets(config_path)
    if target not in targets:
        raise RuntimeError(f"Could not find target '{target}' in {targets} loaded from {config_path}.")
    return targets[target]


def get_targets(config):
    targets = config.getoption('--target')
    if not targets:
        # Default to 'dev'
        return ['dev']
    if "all" in targets:
        config_path = get_targets_ini_path(config)
        return read_targets(config_path).sections()
    return targets


def pytest_report_header(config):
    target_info = []
    targets = get_targets(config)
    for target in targets:
        target_info.append(f"testing target '{target}': {dict(get_target(config, target))}")

    categories_include = set(config.getoption('--category'))
    categories_exclude = set(config.getoption('--category-exclude'))
    target_info.append(f"included categories: {categories_include}")
    target_info.append(f"excluded categories: {categories_exclude}")

    return target_info


def pytest_generate_tests(metafunc):
    targets = get_targets(metafunc.config)
    if "target" in metafunc.fixturenames:
        metafunc.parametrize("target", targets)
    if "target_info" in metafunc.fixturenames:
        metafunc.parametrize("target_info", map(lambda target: get_target(metafunc.config, target), targets), ids=targets)

@pytest.fixture
def categories_include(request):
    return set(request.config.getoption('--category'))

@pytest.fixture
def categories_exclude(request):
    return set(request.config.getoption('--category-exclude'))

@pytest.fixture
def test_category(request):
    def category_test(cat):
        categories_include = set(request.config.getoption('--category'))
        categories_exclude = set(request.config.getoption('--category-exclude'))

        if categories_include:
            # Only include the included categories minus the excluded categories.
            if cat in categories_include and cat not in categories_exclude:
                return True
            return False
        else:
            # Only exclude the categories that are explicitly excluded.
            if cat in categories_exclude:
                return False
            return True

    return category_test


# --issue is consumed by tests/github_issues/conftest.py; this fixture exposes it to any test that wants it.
@pytest.fixture
def selected_github_issues(pytestconfig):
    return pytestconfig.getoption('issue')
