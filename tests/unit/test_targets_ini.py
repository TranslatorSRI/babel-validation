"""targets.ini consistency: moving a target to the other NodeNorm backend means editing
more than its URL, and #154 changed only the URL, which left prod checked as Redis and
fetching an OpenAPI document that 404s on NodeNorm ES."""

import configparser
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

config = configparser.ConfigParser()
config.read(Path(__file__).parent.parent / "targets.ini")


@pytest.mark.parametrize("name", config.sections())
def test_backend_and_openapi_path_agree(name):
    section = config[name]
    is_es = section["NodeNormBackend"] == "elasticsearch"
    uses_default_path = section["NodeNormOpenAPIPath"] == config.defaults()["nodenormopenapipath"]
    assert is_es != uses_default_path, (
        f"[{name}] has NodeNormBackend = {section['NodeNormBackend']} but "
        f"NodeNormOpenAPIPath = {section['NodeNormOpenAPIPath']}: set both when a target "
        f"changes backend."
    )
