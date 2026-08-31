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

import urllib.parse


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
