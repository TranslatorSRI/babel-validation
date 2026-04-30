#
# Tests for the NodeNorm API
# These tests are intended to ensure that all the API endpoints on NodeNorm are working as intended.
#
import urllib.parse
import logging

import pytest
import requests
from openapi_spec_validator import validate_url
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError


def test_openapi_json(target_info):
    nodenorm_url = target_info['NodeNormURL']

    # NodeNorm keeps its openapi.json at /openapi.json, but
    # NodeNorm ES keeps it at /webapp/openapi.json -- so we should check both.

    openapi_paths = [
        'openapi.json',
        'webapp/openapi.json',
    ]

    flag_test_passed = False
    for openapi_path in openapi_paths:
        url = urllib.parse.urljoin(nodenorm_url, openapi_path)
        response = requests.get(url)
        if not response.ok:
            logging.warning(f"Could not GET {url}: {response}")
            continue

        openapi_json = response.json()
        assert openapi_json['info']['x-translator']['infores'] == 'infores:sri-node-normalizer'

        try:
            validate_url(url)
            flag_test_passed = True
        except OpenAPIValidationError as e:
            pytest.fail(f"Could not validate OpenAPI at {url}: {e}")

    if not flag_test_passed:
        pytest.fail(f"Could not validate OpenAPI on NodeNorm {nodenorm_url} at any of the expected URLs: {openapi_paths}")
