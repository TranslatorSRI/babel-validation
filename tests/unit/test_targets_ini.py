"""targets.ini consistency: moving a target to the other NodeNorm backend means editing
more than its URL, and #154 changed only the URL, which left prod checked as Redis and
fetching an OpenAPI document that 404s on NodeNorm ES."""

import configparser
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

config = configparser.ConfigParser()
config.read(Path(__file__).parent.parent / "targets.ini")


OPENAPI_PATH_BY_BACKEND = {
    "redis": "openapi.json",
    "elasticsearch": "webapp/openapi.json",
}


@pytest.mark.parametrize("name", config.sections())
def test_backend_and_openapi_path_agree(name):
    section = config[name]
    backend = section["NodeNormBackend"]
    assert backend in OPENAPI_PATH_BY_BACKEND, f"[{name}] has unknown NodeNormBackend = {backend}"
    assert section["NodeNormOpenAPIPath"] == OPENAPI_PATH_BY_BACKEND[backend], (
        f"[{name}] has NodeNormBackend = {backend} but "
        f"NodeNormOpenAPIPath = {section['NodeNormOpenAPIPath']}: set both when a target "
        f"changes backend."
    )


SERVICE_URL_KEYS = ("NodeNormURL", "NameResURL")


def test_targets_sharing_a_service_say_which_is_the_side_branch():
    # The dashboard's Environments table shows a side branch beside the target it
    # branches from, and learns which that is only from SideBranchOf: a new side
    # branch without it would sit at the far end of the table with nothing to say why.
    for a in config.sections():
        for b in config.sections():
            if a >= b:
                continue
            shared = [
                key for key in SERVICE_URL_KEYS if config[a].get(key) and config[a].get(key) == config[b].get(key)
            ]
            if not shared:
                continue
            declared = config[a].get("SideBranchOf") == b or config[b].get("SideBranchOf") == a
            assert declared, (
                f"[{a}] and [{b}] share {', '.join(shared)}: set SideBranchOf in the "
                f"section that branches from the other."
            )


@pytest.mark.parametrize("name", config.sections())
def test_side_branch_of_names_another_target(name):
    parent = config[name].get("SideBranchOf")
    if parent is None:
        return
    assert parent != name and parent in config.sections(), (
        f"[{name}] has SideBranchOf = {parent}, which is not another section."
    )
