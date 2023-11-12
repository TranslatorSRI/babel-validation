#
# conftest.py - pytest configuration settings
#
import json
import os.path

import pytest
import configparser


def pytest_addoption(parser):
    # The target environment(s) to target.
    parser.addoption(
        '--target',
        default='dev',
        action='append',  # You can specify multiple targets, e.g. `--target prod --target dev`
        help="The target to test. See targets.ini file for a list of targets."
    )


def read_targets(config_path):
    cp = configparser.ConfigParser()
    cp.read(config_path, encoding='utf8')
    return cp


def get_target(config, target):
    config_path = os.path.join(config.rootpath, 'targets.ini')
    targets = read_targets(config_path)
    if target not in targets:
        raise RuntimeError(f"Could not find target '{target}' in {targets} loaded from {config_path}.")
    return targets[target]


def pytest_report_header(config):
    target = config.getoption('--target')

    target_info = [
        f"target: {target}",
        f"target config: {json.dumps(get_target(config, target))}"
    ]
    return target_info


def pytest_generate_tests(metafunc):
    if "target" in metafunc.fixturenames:
        metafunc.parametrize("target", metafunc.config.getoption("--target"))