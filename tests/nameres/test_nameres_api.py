#
# Tests for the NameRes API
# These tests are intended to ensure that all the API endpoints on NameRes are working as intended.
#
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from tests._service_helpers import assert_x_translator, openapi_url

def test_openapi_json(target_info):
    """
    Test the OpenAPI specification.
    """

    url = openapi_url(target_info, 'NameResURL', 'NameResOpenAPIPath')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    openapi_json = response.json()
    assert_x_translator(url, openapi_json, 'infores:sri-name-resolver')

    try:
        # Validate the document we already parsed as JSON, rather than validate_url(url),
        # which re-fetches it and reads it as YAML. YAML 1.1 requires a '.' and a signed
        # exponent in a float, so it parses this service's `1e-06` as the *string*
        # '1e-06' and reports "'1e-06' is not of type 'number'" against a document whose
        # JSON is perfectly valid. That is a spurious failure, and it hid a real one.
        validate(openapi_json, base_uri=url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")


def test_synonyms(target_info):
    """
    Test the /synonyms endpoint, by POST and by GET.

    /synonyms replaced /reverse_lookup (NCATSTranslator/NameResolution#136), which the
    Elasticsearch-backed NameRes does not serve at all.

    :param target_info: The target information for this set of tests.
    """

    nameres_url = target_info['NameResURL']
    synonyms_url = urllib.parse.urljoin(nameres_url, 'synonyms')

    curies_should_work = ['UBERON:8420000']
    curies_should_not_work = ['ENSEMBL:xarg', 'ENSEMBL:ENSDARG00000111928']
    preferred_curies = curies_should_not_work + curies_should_work

    for response in [
        requests.post(synonyms_url, json={'preferred_curies': preferred_curies}),
        requests.get(synonyms_url, params={'preferred_curies': preferred_curies}),
    ]:
        assert response.ok, f"{response.request.method} {synonyms_url} returned {response}"
        response_json = response.json()

        # Confirm that we have an entry for every working CURIE.
        for working_curie in curies_should_work:
            assert response_json[working_curie]['curie'] == working_curie
            assert response_json[working_curie]['preferred_name'] is not None
            assert response_json[working_curie]['preferred_name'] != ''

        # Confirm that every non-working CURIE is represented, with an empty entry.
        for not_working_curie in curies_should_not_work:
            assert response_json[not_working_curie] == {}
