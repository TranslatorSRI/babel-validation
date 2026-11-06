"""Every deployed target in targets.ini must appear in the dashboard's DEPLOYMENT_ORDER.

The promotion order cannot be derived from targets.ini, so it is kept by hand in
website/src/deploymentOrder.js, and a renamed section ([ci-es] became [ci-nameres-es])
left the live dashboard warning that it did not know where the target sat.
"""

import configparser
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).parent.parent.parent

# Run locally against a developer's own services, never in the dashboard workflow.
NOT_DEPLOYED = {"localhost"}


def deployment_order():
    js = (REPO / "website" / "src" / "deploymentOrder.js").read_text()
    match = re.search(r"const DEPLOYMENT_ORDER = \[([^\]]*)\];", js)
    assert match, "could not find DEPLOYMENT_ORDER in deploymentOrder.js"
    return re.findall(r"'([^']*)'", match.group(1))


def test_every_deployed_target_has_a_place_in_the_promotion_order():
    config = configparser.ConfigParser()
    config.read(REPO / "tests" / "targets.ini")
    missing = sorted(set(config.sections()) - NOT_DEPLOYED - set(deployment_order()))
    assert not missing, (
        f"targets.ini defines {missing}, which DEPLOYMENT_ORDER in "
        f"website/src/deploymentOrder.js does not list: add each where it sits in the pipeline."
    )


def test_the_promotion_order_names_only_real_targets():
    config = configparser.ConfigParser()
    config.read(REPO / "tests" / "targets.ini")
    stale = sorted(set(deployment_order()) - set(config.sections()))
    assert (
        not stale
    ), f"DEPLOYMENT_ORDER lists {stale}, which targets.ini no longer defines."
