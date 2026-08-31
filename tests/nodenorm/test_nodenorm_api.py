#
# Tests for the NodeNorm API
# These tests are intended to ensure that all the API endpoints on NodeNorm are working as intended.
#
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate_url
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from tests._service_helpers import assert_backend, assert_x_translator, openapi_url


def test_openapi_json(target_info):
    url = openapi_url(target_info, 'NodeNormURL', 'NodeNormOpenAPIPath')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    assert_x_translator(url, response.json(), 'infores:sri-node-normalizer')

    try:
        validate_url(url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")


def test_status_backend(target_info):
    """
    Test that /status reports the backend this target is configured to be talking to.

    NodeNorm's Redis- and Elasticsearch-backed deployments are both supported, and
    checking that they don't drift apart is a purpose of this repo — so a target moving
    from one to the other should be a deliberate edit to targets.ini, not something
    discovered later through an unrelated test failing for a reason that doesn't name it.

    :param target_info: The target information for this set of tests.
    """
    url = urllib.parse.urljoin(target_info['NodeNormURL'], 'status')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    status_json = response.json()
    expected_backend = target_info.get('NodeNormBackend', 'redis')

    if isinstance(status_json, dict) and 'backend' not in status_json:
        # Only the newer releases report one. Skipping is honest here — the service
        # genuinely cannot answer — but it does mean a green run has not checked this
        # target, so say which one and why.
        pytest.skip(
            f"{url} does not report a backend, so this target cannot be checked against its "
            f"configured backend of {expected_backend!r}. Only newer NodeNorm releases report it."
        )

    assert_backend(url, status_json, expected_backend)
