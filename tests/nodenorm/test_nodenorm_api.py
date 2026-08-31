#
# Tests for the NodeNorm API
# These tests are intended to ensure that all the API endpoints on NodeNorm are working as intended.
#
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate_url
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from tests._service_helpers import assert_x_translator, openapi_url


def test_openapi_json(target_info):
    url = openapi_url(target_info, 'NodeNormURL', 'NodeNormOpenAPIPath')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    assert_x_translator(url, response.json(), 'infores:sri-node-normalizer')

    try:
        validate_url(url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")
