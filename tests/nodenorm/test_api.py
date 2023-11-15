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
    assert openapi_json['info']['x-translator']['infores'] == 'infores:sri-node-normalization'

    try:
        validate_url(url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")
