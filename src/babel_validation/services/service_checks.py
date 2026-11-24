"""Shared checks over the responses NodeNorm and NameRes return, and the URLs we ask for.

Both services are expected to carry an ``info.x-translator`` block in their OpenAPI
document identifying them to SmartAPI, and both come in a Redis/Solr-backed and an
Elasticsearch-backed flavour, which this repo validates against each other. The checks
live here rather than being written out once per service and drifting apart.

Everything these helpers format comes off the network, so it is formatted with
``repr()`` (which escapes control characters, ANSI escapes and bidi overrides) and
truncated before it reaches an assertion message, which pytest keeps in its report.

The one trusted input here is the URL we ask for, which comes from the checked-in
``targets.ini``.

These are test-facing: they fail (or skip) the calling test with ``assert`` and
``pytest.skip``. The release-name parsing they build on needs neither, and is in
``babel_validation.core.babel_release`` for use outside the test suite.
"""

import functools
import re
import urllib.parse

import pytest
import requests

from babel_validation.core.babel_release import babel_release_date, match_babel_version

# The longest repr() we will put into an assertion message, and the most keys we
# will list from an object, so that a service returning something enormous or
# pathological cannot blow up the pytest report.
MAX_REPR_LENGTH = 200
MAX_KEYS_LISTED = 20

# How long to wait for /status or an OpenAPI document, rather than leaving a hung deployment
# to pytest-timeout's 300s.
STATUS_TIMEOUT_SECONDS = 30

# A NodeNorm /status version: a release number, with an optional 'v' and anything after it
# ('1.2.0', 'v1.2.1', '1.3', '1.3.0-rc1', and PEP 440's '1.3.0.dev0' or '1.2.0.post1', since
# NodeNorm ES is a Python project). A fourth number ('1.2.3.4') is not a suffix: rejected.
NODENORM_VERSION = re.compile(r'v?(\d+)\.(\d+)(?:\.(\d+))?(?!\d|\.\d)')


@functools.lru_cache(maxsize=None)
def _fetch_json(url):
    # lru_cache does not cache an exception, so a failed fetch fails this test and is
    # retried by the next one, rather than being remembered for the rest of the run. That
    # is why the JSON-object check is in here too: in a caller, a gateway's brief 200 with
    # `null` would be cached and fail every later test without another fetch. Both /status
    # and an OpenAPI document are JSON objects, so neither caller needs anything else.
    response = requests.get(url, timeout=STATUS_TIMEOUT_SECONDS)
    assert response.ok, f"Could not GET {url}: {response}"
    body = response.json()
    assert isinstance(body, dict), f"{url} did not return a JSON object: {truncated_repr(body)}"
    return body


def get_openapi(target_info, url_key, path_key):
    """
    GET a target's OpenAPI document, and return its URL and the parsed JSON.

    A successful response is cached per URL for the process, so every test that reads
    the document costs one request per target; callers must not modify what is returned.
    Beyond being a JSON object, the document is not checked here, because it is untrusted
    and each caller says what it needs from it.

    :param target_info: The target information for this set of tests.
    :param url_key: The targets.ini key giving the service's base URL.
    :param path_key: The targets.ini key giving the path to the OpenAPI document.
    :return: A tuple of the document's URL and its parsed JSON.
    """
    url = openapi_url(target_info, url_key, path_key)
    return url, _fetch_json(url)


def openapi_url(target_info, url_key, path_key):
    """
    Return the URL of a service's OpenAPI document for a single target.

    The Redis/Solr-backed deployments serve it at FastAPI's default of
    ``openapi.json``; the Elasticsearch-backed ones answer the API itself at the
    root but publish their document at ``webapp/openapi.json`` instead (and serve
    no Swagger UI at ``/docs`` at all). Which applies is per-target configuration:
    both flavours are supported for the foreseeable future, so this is a standing
    difference between deployments rather than a stage of a migration, and it is
    not something to guess at from the hostname.

    :param target_info: The target information for this set of tests.
    :param url_key: The targets.ini key giving the service's base URL.
    :param path_key: The targets.ini key giving the path to the OpenAPI document.
    :return: The URL of the OpenAPI document.
    """
    return urllib.parse.urljoin(target_info[url_key], target_info.get(path_key, 'openapi.json'))


def truncated_repr(value, max_length=MAX_REPR_LENGTH):
    """
    Return ``repr(value)``, truncated to a length safe to put in a test report.

    :param value: The value to represent.
    :param max_length: The maximum number of characters of the repr() to keep.
    :return: The (possibly truncated) repr() of value.
    """
    text = repr(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}... ({len(text)} characters, truncated to {max_length})"


def truncated_keys_repr(mapping, max_keys=MAX_KEYS_LISTED):
    """
    Return a truncated repr() of a JSON object's keys, sorted.

    :param mapping: The dictionary whose keys should be listed.
    :param max_keys: The maximum number of keys to list.
    :return: The (possibly truncated) repr() of the sorted keys.
    """
    keys = sorted(mapping)
    text = truncated_repr(keys[:max_keys])
    if len(keys) > max_keys:
        text += f" (+{len(keys) - max_keys} more)"
    return text


def assert_x_translator(url, openapi_json, expected_infores):
    """
    Assert that an OpenAPI document carries the info.x-translator block Translator requires.

    Each step is checked on its own so that the failure says what is actually
    wrong: a block that is absent and a block that is present but malformed have
    different causes and different fixes, and reaching into a value that isn't a
    JSON object would otherwise raise a bare AttributeError or TypeError instead
    of reporting anything useful.

    :param url: The URL the document was retrieved from, for the error messages.
    :param openapi_json: The parsed OpenAPI document.
    :param expected_infores: The infores identifier this service should declare.
    """
    assert isinstance(openapi_json, dict), (
        f"{url} did not return a JSON object: {truncated_repr(openapi_json)}"
    )

    assert 'info' in openapi_json, (
        f"{url} has no info block (top-level keys: {truncated_keys_repr(openapi_json)})."
    )
    info = openapi_json['info']
    assert isinstance(info, dict), (
        f"{url} has an info that is not a JSON object: {truncated_repr(info)}"
    )

    assert 'x-translator' in info, (
        f"{url} has no info.x-translator block (info keys: {truncated_keys_repr(info)}). Every "
        f"Translator service needs one to be registered in SmartAPI; a service that is missing it "
        f"altogether is usually serving FastAPI's default OpenAPI document instead of its own "
        f"openapi.yml."
    )
    x_translator = info['x-translator']
    assert isinstance(x_translator, dict), (
        f"{url} has an info.x-translator that is not a JSON object: {truncated_repr(x_translator)}"
    )

    assert x_translator.get('infores') == expected_infores, (
        f"{url} declares info.x-translator.infores as "
        f"{truncated_repr(x_translator.get('infores'))}, expected {expected_infores!r}."
    )


def assert_backend(url, status_json, expected_backend):
    """
    Assert that a service's /status reports the backend its target says it should be.

    Both the Redis- and the Elasticsearch-backed deployments are supported, and
    checking one against the other is a purpose of this repo, so which one a target
    points at is a deliberate choice that should be stated in targets.ini and held
    to. Deployments predating the `backend` field can't answer, and are skipped
    rather than assumed: see the caller, which owns that decision.

    :param url: The URL the status was retrieved from, for the error messages.
    :param status_json: The parsed /status response.
    :param expected_backend: The backend this target is configured to be talking to.
    """
    assert isinstance(status_json, dict), (
        f"{url} did not return a JSON object: {truncated_repr(status_json)}"
    )

    assert status_json.get('backend') == expected_backend, (
        f"{url} reports backend {truncated_repr(status_json.get('backend'))}, but this target is "
        f"configured as {expected_backend!r}. Either the deployment was repointed at the other "
        f"backend, in which case targets.ini needs to follow it (including the path to its "
        f"OpenAPI document), or it is answering from somewhere unexpected."
    )


def parse_babel_version(url, status_json):
    """
    Assert that /status reports a well-formed babel_version, and return it.

    :param url: The URL the status was retrieved from, for the error messages.
    :param status_json: The parsed /status response.
    :return: The babel_version, which is safe to build a URL from.
    """
    assert 'babel_version' in status_json, f"{url} does not report a babel_version."
    babel_version = status_json['babel_version']

    assert match_babel_version(babel_version), (
        f"{url} reports babel_version {truncated_repr(babel_version)}, which is not a Babel "
        f"release name such as '2026sep24' or '2026sep24-dev'."
    )
    assert babel_release_date(babel_version) is not None, (
        f"{url} reports babel_version {babel_version!r}, which is not a real date."
    )

    return babel_version


def get_status(target_info):
    """
    GET a target's NodeNorm /status, and return its URL and the JSON object it returned.

    Fails the calling test if /status cannot be fetched or is not a JSON object. A
    successful response is cached per URL for the process, so every test that asks costs
    one request per target; callers must not modify the returned dict.

    :param target_info: The target information for this set of tests.
    :return: A tuple of the /status URL and its parsed response.
    """
    status_url = urllib.parse.urljoin(target_info['NodeNormURL'], 'status')
    return status_url, _fetch_json(status_url)


def nodenorm_version(target_info):
    """
    Return the NodeNorm release a target's /status reports, as a tuple of three ints.

    Accepts '1.2.0', 'v1.2.0', '1.2' (as (1, 2, 0)) and a suffixed '1.3.0-rc1', '1.3.0.dev0'
    or '1.2.0.post1'. The suffix is ignored, so a pre-release of 1.3.0 compares as 1.3.0: a
    version gate is asking whether a fix is in, and a release candidate for the release that
    fixed it normally has it. A target that reports no version we can read fails rather than guessing which side
    of a gate it is on.

    :param target_info: The target information for this set of tests.
    :return: The version as (major, minor, patch).
    """
    status_url, status_json = get_status(target_info)
    version = status_json.get('version')
    match = NODENORM_VERSION.match(version) if isinstance(version, str) else None
    assert match, (
        f"{status_url} reports no NodeNorm release number such as '1.2.0': "
        f"{truncated_repr(version)}"
    )
    return tuple(int(part or 0) for part in match.groups())


def require_babel_release(target_info, minimum_version):
    """
    Skip the calling test unless the target serves Babel ``minimum_version`` or later.

    For a test whose expectations are only true of the data from one Babel release on
    (a compendium that did not exist before it, a clique that was rearranged by it).
    A target whose /status cannot be fetched, or that does not report a well-formed
    babel_version, fails rather than skips: we cannot tell whether the test applies, and
    a skip would make a run look green that had tested nothing.

    :param target_info: The target information for this set of tests.
    :param minimum_version: The earliest Babel release name the test is valid for.
    """
    minimum_date = babel_release_date(minimum_version)
    assert minimum_date is not None, f"{minimum_version!r} is not a Babel release name"

    status_url, status_json = get_status(target_info)
    babel_version = parse_babel_version(status_url, status_json)
    if babel_release_date(babel_version) < minimum_date:
        pytest.skip(
            f"{status_url} serves Babel {babel_version}; this test needs {minimum_version} or later"
        )


def get_normalized_node(target_info, curie, **params):
    """
    POST one CURIE to a target's get_normalized_nodes, and return its node.

    Asserts the response is an object whose entry for curie is itself an object, so that
    an unexpected shape fails with a readable message rather than an AttributeError.

    :param target_info: The target information for this set of tests.
    :param curie: The CURIE to normalize.
    :param params: Further request parameters; conflate defaults to False.
    :return: The normalized node for curie.
    """
    url = urllib.parse.urljoin(target_info['NodeNormURL'], 'get_normalized_nodes')
    response = requests.post(url, json={'curies': [curie], 'conflate': False, **params})
    assert response.ok, (
        f"POST {url} returned HTTP {response.status_code}: {truncated_repr(response.text)}"
    )
    result = response.json()
    assert isinstance(result, dict), f"{url} did not return a JSON object: {truncated_repr(result)}"
    node = result.get(curie)
    assert node is not None, f"{curie} is not normalizable on {url}"
    assert isinstance(node, dict), f"{url} returned a non-object for {curie}: {truncated_repr(node)}"
    return node
