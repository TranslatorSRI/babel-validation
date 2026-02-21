#
# conftest.py - pytest configuration settings
#
import glob
import os
import os.path
import tempfile

import pytest
import configparser


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


def pytest_configure(config):
    # Delete the Google Sheet CSV cache at the start of each run so tests always
    # use a fresh download. Only the controller does this — xdist workers skip it
    # so they can share the cache file written by the controller.
    if not os.environ.get('PYTEST_XDIST_WORKER'):
        for f in glob.glob(os.path.join(tempfile.gettempdir(), 'babel_validation_gsheet_*.csv')):
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass
        try:
            os.unlink(os.path.join(tempfile.gettempdir(), 'babel_validation_issues_cache.json'))
        except FileNotFoundError:
            pass


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

    # The issue option is only used by
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

# Issue is only used by the GitHub issue tests (tests/github_issues/*)
@pytest.fixture
def selected_github_issues(pytestconfig):
    return pytestconfig.getoption('issue')
