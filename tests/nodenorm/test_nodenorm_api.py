#
# Tests for the NodeNorm API
# These tests are intended to ensure that all the API endpoints on NodeNorm are working as intended.
#
import datetime
import re
import urllib.parse

import pytest
import requests
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from tests._service_helpers import assert_backend, assert_x_translator, openapi_url, truncated_repr

# The backends a NodeNorm deployment can report in /status.
KNOWN_BACKENDS = {'redis', 'elasticsearch'}

# Babel releases are named for the day they were made, e.g. '2026sep24', optionally with an
# alphanumeric suffix after a hyphen, e.g. '2026sep24-dev'. Each part is a fixed width or a
# disjoint character class, so there is nothing here to backtrack over.
BABEL_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
BABEL_VERSION_RE = re.compile(
    r'(?P<year>\d{4})(?P<month>' + '|'.join(BABEL_MONTHS) + r')(?P<day>\d{1,2})(?:-[A-Za-z0-9]+)?'
)
BABEL_VERSION_MAX_LENGTH = 64

# Where each Babel release's notes are published. NodeNorm links to them on `master`,
# which GitHub redirects now that Babel's default branch is `main`; either is correct.
BABEL_RELEASE_NOTES_URL = 'https://github.com/ncatstranslator/Babel/blob/{branch}/releases/{version}.md'
BABEL_RELEASE_NOTES_BRANCHES = ('main', 'master')


def test_openapi_json(target_info):
    url = openapi_url(target_info, 'NodeNormURL', 'NodeNormOpenAPIPath')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    openapi_json = response.json()
    assert_x_translator(url, openapi_json, 'infores:sri-node-normalizer')

    try:
        # Validate the document we already parsed as JSON, rather than validate_url(url),
        # which re-fetches it and reads it as YAML. YAML 1.1 requires a '.' and a signed
        # exponent in a float, so it parses this service's `1e-06` as the *string*
        # '1e-06' and reports "'1e-06' is not of type 'number'" against a document whose
        # JSON is perfectly valid. That is a spurious failure, and it hid a real one.
        validate(openapi_json, base_uri=url)
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


def get_status(target_info):
    """
    GET a target's /status, and return its URL and the JSON object it returned.

    :param target_info: The target information for this set of tests.
    :return: A tuple of the /status URL and its parsed response.
    """
    url = urllib.parse.urljoin(target_info['NodeNormURL'], 'status')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    status_json = response.json()
    assert isinstance(status_json, dict), (
        f"{url} did not return a JSON object: {truncated_repr(status_json)}"
    )
    return url, status_json


def parse_babel_version(url, status_json):
    """
    Assert that /status reports a well-formed babel_version, and return it.

    :param url: The URL the status was retrieved from, for the error messages.
    :param status_json: The parsed /status response.
    :return: The babel_version, which is safe to build a URL from.
    """
    assert 'babel_version' in status_json, f"{url} does not report a babel_version."
    babel_version = status_json['babel_version']

    match = None
    if isinstance(babel_version, str) and len(babel_version) <= BABEL_VERSION_MAX_LENGTH:
        match = BABEL_VERSION_RE.fullmatch(babel_version)
    assert match, (
        f"{url} reports babel_version {truncated_repr(babel_version)}, which is not a Babel "
        f"release name such as '2026sep24' or '2026sep24-dev'."
    )

    try:
        datetime.date(
            int(match['year']), BABEL_MONTHS.index(match['month']) + 1, int(match['day'])
        )
    except ValueError:
        pytest.fail(f"{url} reports babel_version {babel_version!r}, which is not a real date.")

    return babel_version


def test_status_backend_is_known(target_info):
    """
    Test that /status reports its backend, and that it is one NodeNorm has.

    Unlike test_status_backend, which skips a deployment that does not report a backend
    because it cannot be checked against targets.ini, this fails it: every current
    NodeNorm release reports one, so a deployment that doesn't is out of date.

    :param target_info: The target information for this set of tests.
    """
    url, status_json = get_status(target_info)

    assert 'backend' in status_json, (
        f"{url} does not report a backend: it should be one of {sorted(KNOWN_BACKENDS)}."
    )
    assert status_json['backend'] in KNOWN_BACKENDS, (
        f"{url} reports backend {truncated_repr(status_json['backend'])}, which is not one of "
        f"{sorted(KNOWN_BACKENDS)}."
    )


def test_status_babel_version(target_info):
    """
    Test that /status reports the Babel release it is serving, by its release name.

    :param target_info: The target information for this set of tests.
    """
    url, status_json = get_status(target_info)
    parse_babel_version(url, status_json)


def test_status_babel_version_url(target_info):
    """
    Test that /status links to the release notes for the Babel release it is serving.

    We never fetch the babel_version_url as given, since it comes off the network: we
    build the URL we expect from the (validated) babel_version, check that that is the
    one reported, and fetch ours. The notes are sometimes written after a release is
    deployed, so a brand-new release fails here until they are published.

    :param target_info: The target information for this set of tests.
    """
    url, status_json = get_status(target_info)
    babel_version = parse_babel_version(url, status_json)
    expected_urls = [
        BABEL_RELEASE_NOTES_URL.format(branch=branch, version=babel_version)
        for branch in BABEL_RELEASE_NOTES_BRANCHES
    ]
    expected_url = expected_urls[0]

    assert 'babel_version_url' in status_json, f"{url} does not report a babel_version_url."
    babel_version_url = status_json['babel_version_url']
    assert isinstance(babel_version_url, str) and babel_version_url.casefold() in [
        u.casefold() for u in expected_urls
    ], (
        f"{url} reports babel_version_url {truncated_repr(babel_version_url)}, but the release "
        f"notes for {babel_version!r} are at {expected_url}."
    )

    response = requests.get(expected_url)
    assert response.ok, (
        f"{url} links to the release notes for Babel {babel_version!r}, but GET {expected_url} "
        f"returned {response}. If this release is new, its notes may not have been published yet."
    )
