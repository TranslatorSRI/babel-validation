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
    assert (
        backend in OPENAPI_PATH_BY_BACKEND
    ), f"[{name}] has unknown NodeNormBackend = {backend}"
    assert section["NodeNormOpenAPIPath"] == OPENAPI_PATH_BY_BACKEND[backend], (
        f"[{name}] has NodeNormBackend = {backend} but "
        f"NodeNormOpenAPIPath = {section['NodeNormOpenAPIPath']}: set both when a target "
        f"changes backend."
    )
