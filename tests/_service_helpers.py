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
"""

import functools
import re
import urllib.parse

import pytest
import requests

# The longest repr() we will put into an assertion message, and the most keys we
# will list from an object, so that a service returning something enormous or
# pathological cannot blow up the pytest report.
MAX_REPR_LENGTH = 200
MAX_KEYS_LISTED = 20


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


# A release tag as NameRes reports it in /status, e.g. `v1.7.1`. A pre-release or build
# suffix (`v1.7.1-rc1`) is accepted and ignored, so a release candidate counts as the
# release it leads up to. The digit runs and the dots cannot match each other's
# characters, so this cannot backtrack badly on a hostile string -- which is also
# bounded before we try it.
VERSION_PATTERN = re.compile(r"v?(\d+(?:\.\d+)*)(?:[-+][0-9A-Za-z.-]*)?")
MAX_VERSION_LENGTH = 64


def parse_version(text):
    """
    Parse a release tag like ``v1.7.1`` into a tuple of integers, such as ``(1, 7, 1)``.

    :param text: The version string, as reported by a service.
    :return: The tuple of version components, or None if text is not a version.
    """
    if not isinstance(text, str) or len(text) > MAX_VERSION_LENGTH:
        return None
    match = VERSION_PATTERN.fullmatch(text.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split('.'))


def nameres_version_shortfall(url, status_json, minimum, feature):
    """
    Explain why a NameRes /status shows a deployment too old for a feature, if it does.

    A NameRes that predates a query parameter does not reject it: FastAPI drops
    parameters it doesn't know, and answers with a 200 as though it had never been
    sent. So a feature cannot be detected by trying it -- an old server "supports" it
    and silently searches without it -- and must be gated on the version the server
    reports instead. A deployment that reports no version at all (older releases, and
    the Elasticsearch-backed NameLookup) is treated as too old.

    :param url: The URL the status was retrieved from, for the messages.
    :param status_json: The parsed /status response.
    :param minimum: The first version with the feature, as a tuple such as (1, 7, 1).
    :param feature: What needs that version, for the messages.
    :return: None if the deployment is new enough, otherwise a reason to skip.
    :raises AssertionError: If the status is malformed or its version unparseable:
        that is a broken deployment, and skipping would make it look like a pass.
    """
    minimum_text = 'v' + '.'.join(str(part) for part in minimum)
    assert isinstance(status_json, dict), (
        f"{url} did not return a JSON object: {truncated_repr(status_json)}"
    )

    reported = status_json.get('nameres_version')
    if reported is None:
        return (
            f"{url} does not report a nameres_version, so it cannot be relied on to support "
            f"{feature}, which needs NameRes {minimum_text} or later."
        )

    version = parse_version(reported)
    assert version is not None, (
        f"{url} reports a nameres_version of {truncated_repr(reported)}, which is not a "
        f"version, so we cannot tell whether it supports {feature}."
    )

    if version < tuple(minimum):
        return (
            f"{url} reports NameRes {truncated_repr(reported)}, but {feature} needs "
            f"{minimum_text} or later."
        )
    return None


@functools.cache
def fetch_status(status_url):
    """
    Return a service's parsed /status response, fetched once per URL per process.

    Every test gated on a version asks for this, so without the cache a gated module
    would fetch /status once per test (and per parametrized row).

    :param status_url: The URL of the /status endpoint, from targets.ini.
    :return: The parsed JSON response.
    """
    response = requests.get(status_url, timeout=30)
    response.raise_for_status()
    return response.json()


def require_nameres_version(target_info, minimum, feature):
    """
    Skip the calling test unless this target's NameRes is at least version *minimum*.

    See nameres_version_shortfall() for why this checks the reported version rather
    than probing for the feature.

    :param target_info: The target information for this set of tests.
    :param minimum: The first version with the feature, as a tuple such as (1, 7, 1).
    :param feature: What needs that version, for the skip message.
    """
    url = urllib.parse.urljoin(target_info['NameResURL'], 'status')
    reason = nameres_version_shortfall(url, fetch_status(url), minimum, feature)
    if reason:
        pytest.skip(reason)
