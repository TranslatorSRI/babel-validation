#
# Tests for the NameRes API
# These tests are intended to ensure that all the API endpoints on NameRes are working as intended.
#
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from babel_validation.services.service_checks import assert_x_translator, get_openapi


def test_openapi_json(target_info):
    """
    Test the OpenAPI specification.
    """

    url, openapi_json = get_openapi(target_info, "NameResURL", "NameResOpenAPIPath")
    assert_x_translator(url, openapi_json, "infores:sri-name-resolver")

    try:
        # Validate the document we already parsed as JSON, rather than validate_url(url),
        # which re-fetches it and reads it as YAML. YAML 1.1 requires a '.' and a signed
        # exponent in a float, so it parses this service's `1e-06` as the *string*
        # '1e-06' and reports "'1e-06' is not of type 'number'" against a document whose
        # JSON is perfectly valid. That is a spurious failure, and it hid a real one.
        validate(openapi_json, base_uri=url)
    except OpenAPIValidationError as e:
        pytest.fail(f"Could not validate OpenAPI at {url}: {e}")


# Each request gets its own timeout, so a hung service fails here, naming the request,
# rather than at pytest's 300s limit with nothing to say which call it was stuck on.
NAMERES_TIMEOUT = 30

CURIES_SHOULD_WORK = ["UBERON:8420000"]
CURIES_SHOULD_NOT_WORK = ["ENSEMBL:xarg", "ENSEMBL:ENSDARG00000111928"]


def check_curie_lookup(url, param):
    """
    POST and then GET `url` with every test CURIE under `param`, checking each response
    before sending the next: a filled entry for every CURIE that resolves, and an empty
    one for every CURIE that does not.
    """
    curies = CURIES_SHOULD_NOT_WORK + CURIES_SHOULD_WORK
    for method, kwargs in [
        ("POST", {"json": {param: curies}}),
        ("GET", {"params": {param: curies}}),
    ]:
        response = requests.request(method, url, timeout=NAMERES_TIMEOUT, **kwargs)
        assert response.ok, f"{method} {url} returned {response}"
        response_json = response.json()

        for working_curie in CURIES_SHOULD_WORK:
            assert response_json[working_curie]["curie"] == working_curie
            assert response_json[working_curie]["preferred_name"] is not None
            assert response_json[working_curie]["preferred_name"] != ""

        for not_working_curie in CURIES_SHOULD_NOT_WORK:
            assert response_json[not_working_curie] == {}


def test_synonyms(target_info):
    """
    Test the /synonyms endpoint, by POST and by GET.

    /synonyms replaced /reverse_lookup (NCATSTranslator/NameResolution#136).

    :param target_info: The target information for this set of tests.
    """
    check_curie_lookup(urllib.parse.urljoin(target_info["NameResURL"], "synonyms"), "preferred_curies")


def test_reverse_lookup(target_info, request):
    """
    Test the deprecated /reverse_lookup endpoint, by POST and by GET.

    The Solr-backed NameRes still serves it and clients still call it, so a regression
    there matters. The Elasticsearch-backed NameRes does not serve it at all (a 404):
    that is a difference between the two flavours, which is exactly what this repo
    exists to report, so it is a strict xfail rather than a deleted test. If the ES
    NameRes gains the endpoint, the XPASS says this mark can go.

    :param target_info: The target information for this set of tests.
    """
    if target_info.get("NameResBackend", "solr") == "elasticsearch":
        # applymarker, not pytest.xfail(): that stops the test unrun, so it could never XPASS.
        request.applymarker(
            pytest.mark.xfail(
                strict=True,
                reason="The Elasticsearch-backed NameRes does not serve /reverse_lookup; use /synonyms.",
            )
        )
    check_curie_lookup(urllib.parse.urljoin(target_info["NameResURL"], "reverse_lookup"), "curies")
