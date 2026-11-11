"""Every deployed target in targets.ini must appear in the dashboard's DEPLOYMENT_ORDER.

The promotion order cannot be derived from targets.ini, so it is kept by hand in
website/src/deploymentOrder.js, and a renamed section ([ci-es] became [ci-nameres-es])
left the live dashboard warning that it did not know where the target sat.
"""

import re
from pathlib import Path

import pytest

from babel_validation.tools.generate_report import read_targets

pytestmark = pytest.mark.unit

REPO = Path(__file__).parent.parent.parent

# The deployed targets: what the dashboard workflow runs and the site shows. Taken from
# read_targets() so that what counts as "not deployed" (localhost) is decided in one place.
DEPLOYED, _, _ = read_targets(REPO / "tests" / "targets.ini")


def deployment_order():
    js = (REPO / "website" / "src" / "deploymentOrder.js").read_text(encoding="utf8")
    match = re.search(r"const DEPLOYMENT_ORDER = \[([^\]]*)\];", js)
    assert match, "could not find DEPLOYMENT_ORDER in deploymentOrder.js"
    # Drop comments first, so a quoted word in one is not read as a target name.
    body = re.sub(r"//[^\n]*|/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    names = re.findall(r"""(['"])(.*?)\1""", body)
    # Otherwise a reformat this regex does not follow reports every target as missing.
    assert names, f"could not read any names from DEPLOYMENT_ORDER: {match.group(0)!r}"
    return [name for _, name in names]


def test_every_deployed_target_has_a_place_in_the_promotion_order():
    missing = sorted(set(DEPLOYED) - set(deployment_order()))
    assert not missing, (
        f"targets.ini defines {missing}, which DEPLOYMENT_ORDER in "
        f"website/src/deploymentOrder.js does not list: add each where it sits in the pipeline."
    )


def test_the_promotion_order_names_only_deployed_targets():
    stale = sorted(set(deployment_order()) - set(DEPLOYED))
    assert not stale, f"DEPLOYMENT_ORDER lists {stale}, which are not deployed targets in targets.ini."
