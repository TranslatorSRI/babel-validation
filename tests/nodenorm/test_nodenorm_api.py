#
# Tests for the NodeNorm API
# These tests are intended to ensure that all the API endpoints on NodeNorm are working as intended.
#
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate_url
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError


def test_openapi_json(target_info):
    nodenorm_url = target_info['NodeNormURL']

    url = urllib.parse.urljoin(nodenorm_url, 'openapi.json')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    openapi_json = response.json()
    info = openapi_json.get('info', {})
    assert isinstance(info.get('x-translator'), dict), (
        f"{url} has no info.x-translator block (info keys: {sorted(info)!r}). Every Translator "
        f"service needs one to be registered in SmartAPI; a service that is missing it altogether "
        f"is usually serving FastAPI's default OpenAPI document instead of its own openapi.yml."
    )
    assert info['x-translator'].get('infores') == 'infores:sri-node-normalizer', (
        f"{url} declares info.x-translator.infores as {info['x-translator'].get('infores')!r}, "
        f"expected 'infores:sri-node-normalizer'."
    )

    try:
        validate_url(url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")
