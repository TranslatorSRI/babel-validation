"""
Check that each NodeNorm deployment answers its endpoints the way its OpenAPI document says.

NodeNorm Redis and NodeNorm ES are meant to be interchangeable for the endpoints they share,
and these tests hold each deployment to the response shapes clients were written against. They
were added for three discrepancies found on NodeNorm ES: /get_allowed_conflations returned HTTP
500, POST /get_setid returned an index-keyed object instead of a list, and /get_semantic_types
lower-cased every Biolink class. biothings/NodeNormalizationAPI#58 fixed the first and most of
the third, in NodeNorm ES 1.2.0, which not every ES target runs yet. What is left is a strict
xfail on the Elasticsearch targets, and an unexpected pass is the signal to drop the marker.

Everything a deployment returns is untrusted, its OpenAPI document included: it is formatted
with truncated_repr(), and the document's path keys are validated before any URL is built from
them.
"""

import re
import urllib.parse

import pytest
import requests

from src.babel_validation.services.service_checks import (
    get_normalized_node,
    get_openapi,
    nodenorm_version,
    truncated_repr,
)

# Every request has a timeout, so a stalled endpoint fails with its own URL in the message
# instead of holding the test until pytest-timeout's limit says nothing more useful.
REQUEST_TIMEOUT = 30

# The endpoints both backends serve. NodeNorm Redis also has the TRAPI endpoints /query and
# /asyncquery and /get_curie_prefixes, which NodeNorm ES deliberately leaves out
# (biothings/NodeNormalizationAPI#36); NodeNorm ES also has /version.
SHARED_PATHS = {
    "/status",
    "/get_normalized_nodes",
    "/get_setid",
    "/get_semantic_types",
    "/get_allowed_conflations",
}

# The OpenAPI document comes off the network, so its path keys decide nothing about where we
# send a request until they pass this: plain segments of letters, digits, '_' and '-'. That
# rules out '//host/x', '/https://host/x' and '..', which urljoin() would otherwise follow off
# the deployment, and templated paths like '/x/{id}', which we would have no value to fill in.
SAFE_PATH = re.compile(r"(?:/[A-Za-z0-9_-]+)+")
# Neither backend documents more than ten paths; this bounds how many requests a document can
# make us send.
MAX_DOCUMENTED_PATHS = 50

# The NodeNorm ES release, as /status reports its version, that fixed /get_allowed_conflations
# answering HTTP 500 (biothings/NodeNormalizationAPI#58). On 2026-11-06 ci and test ran 1.2.0
# and prod 1.0.0; once every ES target reports 1.2.0 or later, drop the `before=` uses.
NODENORM_ES_CONFLATIONS_FIX = (1, 2, 0)


class KnownElasticsearchDiscrepancy(AssertionError):
    """
    Raised only by the one check that a known NodeNorm ES discrepancy fails.

    The strict xfail on the Elasticsearch targets passes ``raises=`` this class rather than
    AssertionError, so a deployment that is down, a body that isn't JSON, or a shape check
    before the known one fails the test as it would anywhere else, instead of reading as the
    discrepancy we expected.
    """


def elasticsearch_discrepancy_applies(target_info, before=None):
    """
    Whether a known NodeNorm ES discrepancy is expected on this target: on every ES target, or
    with ``before``, only on those whose /status version is older than it, because the fix has
    been released and the targets already running it must pass.
    """
    if target_info.get("NodeNormBackend", "redis") != "elasticsearch":
        return False
    return before is None or nodenorm_version(target_info) < before


def conflations_500_expected(target_info):
    return elasticsearch_discrepancy_applies(
        target_info, before=NODENORM_ES_CONFLATIONS_FIX
    )


def expect_elasticsearch_discrepancy(request, target_info, reason, before=None):
    """
    Mark the calling test a strict xfail for KnownElasticsearchDiscrepancy only, on the targets
    elasticsearch_discrepancy_applies() picks out.
    """
    if elasticsearch_discrepancy_applies(target_info, before):
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True, raises=KnownElasticsearchDiscrepancy, reason=reason
            )
        )


def test_get_allowed_conflations(request, target_info):
    expect_elasticsearch_discrepancy(
        request,
        target_info,
        "/get_allowed_conflations returns HTTP 500 before NodeNorm ES 1.2.0 "
        "(biothings/NodeNormalizationAPI#58)",
        before=NODENORM_ES_CONFLATIONS_FIX,
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_allowed_conflations")
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 500 and conflations_500_expected(target_info):
        # Tornado's bare error page is all the bug returns, and an ES outage would return the
        # same page. So count the 500 as the known bug only if normalization, which also needs
        # ES, still works; otherwise the deployment is broken in some new way.
        assert "500: Internal Server Error" in response.text, (
            f"GET {url} returned HTTP 500, but not the error page the known bug returns: "
            f"{truncated_repr(response.text)}"
        )
        get_normalized_node(target_info, "MESH:D014867")
        raise KnownElasticsearchDiscrepancy(f"GET {url} returned HTTP 500")
    assert (
        response.ok
    ), f"Could not GET {url}: HTTP {response.status_code} {truncated_repr(response.text)}"
    body = response.json()
    assert isinstance(body, dict) and isinstance(
        body.get("conflations"), list
    ), f"{url} should return an object with a 'conflations' list, got {truncated_repr(body)}"
    assert {"GeneProtein", "DrugChemical"} <= set(body["conflations"]), truncated_repr(
        body
    )


def test_get_semantic_types_are_biolink_classes(request, target_info):
    # This requires the Biolink Model's casing, which is what NodeNorm Redis returns and what
    # clients comparing categories as strings expect. Whether biolink:smallmolecule would also be
    # an acceptable spelling is TranslatorSRI/babel-validation#158; don't relax this before that
    # is decided.
    expect_elasticsearch_discrepancy(
        request,
        target_info,
        "/get_semantic_types lists lower-cased classes such as biolink:smallmolecule "
        "(biothings/NodeNormalizationAPI#59)",
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_semantic_types")
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    assert (
        response.ok
    ), f"Could not GET {url}: HTTP {response.status_code} {truncated_repr(response.text)}"
    body = response.json()
    semantic_types = body.get("semantic_types") if isinstance(body, dict) else None
    types = semantic_types.get("types") if isinstance(semantic_types, dict) else None
    assert isinstance(
        types, list
    ), f"{url} should return {{'semantic_types': {{'types': [...]}}}}, got {truncated_repr(body)}"
    assert types, f"{url} returned no semantic types"

    not_classes = [
        t
        for t in types
        if not (isinstance(t, str) and re.fullmatch(r"biolink:[A-Z][A-Za-z]*", t))
    ]
    # Only an all-lower-case class name is the known bug; anything else that isn't a Biolink
    # class CURIE is a new failure, and must not be absorbed by the xfail.
    lower_cased = [
        t
        for t in not_classes
        if isinstance(t, str) and re.fullmatch(r"biolink:[a-z]+", t)
    ]
    malformed = [t for t in not_classes if t not in lower_cased]
    assert not malformed, (
        f"{url} returned {len(malformed)} types that are not Biolink class CURIEs: "
        f"{truncated_repr(malformed)}"
    )
    if lower_cased:
        raise KnownElasticsearchDiscrepancy(
            f"{url} returned {len(lower_cased)} lower-cased Biolink classes: "
            f"{truncated_repr(lower_cased)}"
        )


def test_get_setid_post_returns_list(request, target_info):
    """
    POST /get_setid answers with a list, one set-ID result per input set.

    Only the shape is checked here: test_setid_basic in test_nodenorm_setid.py checks the set
    IDs themselves, from both GET and POST.
    """
    expect_elasticsearch_discrepancy(
        request,
        target_info,
        "POST /get_setid returns an object keyed by input index "
        "(biothings/NodeNormalizationAPI#48)",
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_setid")
    sets = [
        {"curies": ["MESH:D014867", "NCIT:C34373"]},
        {
            "curies": ["NCIT:C34373", "MESH:D014867", "RUBBISH:1234"],
            "conflations": ["GeneProtein"],
        },
    ]
    response = requests.post(url, json=sets, timeout=REQUEST_TIMEOUT)
    assert (
        response.ok
    ), f"Could not POST to {url}: HTTP {response.status_code} {truncated_repr(response.text)}"

    body = response.json()
    # The known bug is the list we expect, keyed by index instead: '0', '1', ... with a set-ID
    # result under each. Any other object (an error, say) falls through to the list check below.
    if (
        isinstance(body, dict)
        and set(body) == {str(i) for i in range(len(sets))}
        and all(
            isinstance(r, dict) and isinstance(r.get("setid"), str)
            for r in body.values()
        )
    ):
        raise KnownElasticsearchDiscrepancy(
            f"POST {url} should return a list, got an object: {truncated_repr(body)}"
        )
    assert isinstance(body, list) and len(body) == len(
        sets
    ), f"POST {url} should return one result per input set as a list, got {truncated_repr(body)}"
    for result in body:
        assert isinstance(result, dict) and isinstance(
            result.get("setid"), str
        ), f"POST {url} returned a result with no set ID: {truncated_repr(result)}"


def get_documented_paths(target_info):
    doc_url, document = get_openapi(target_info, "NodeNormURL", "NodeNormOpenAPIPath")
    assert isinstance(document, dict) and isinstance(
        document.get("paths"), dict
    ), f"{doc_url} has no 'paths' object: {truncated_repr(document)}"
    return doc_url, set(document["paths"])


def test_documents_every_shared_endpoint(target_info):
    """The published OpenAPI document lists every endpoint both backends are meant to serve."""
    doc_url, paths = get_documented_paths(target_info)
    missing = sorted(SHARED_PATHS - paths)
    assert (
        not missing
    ), f"{doc_url} does not document endpoints every NodeNorm serves: {missing!r}"


def test_every_documented_path_is_served(request, target_info):
    """Every path in the published OpenAPI document answers a bare GET with neither a 404 nor a
    5xx. Anything else counts as served: a POST-only endpoint answers 405, and one with required
    parameters 400 or 422."""
    expect_elasticsearch_discrepancy(
        request,
        target_info,
        "/get_allowed_conflations returns HTTP 500 before NodeNorm ES 1.2.0 "
        "(biothings/NodeNormalizationAPI#58)",
        before=NODENORM_ES_CONFLATIONS_FIX,
    )
    doc_url, paths = get_documented_paths(target_info)

    unsafe = sorted(p for p in paths if not SAFE_PATH.fullmatch(p))
    assert (
        not unsafe
    ), f"{doc_url} documents paths we will not build a URL from: {truncated_repr(unsafe)}"
    assert len(paths) <= MAX_DOCUMENTED_PATHS, (
        f"{doc_url} documents {len(paths)} paths, more than the {MAX_DOCUMENTED_PATHS} "
        f"this test will request"
    )

    not_served = []
    for path in sorted(paths):
        url = urllib.parse.urljoin(target_info["NodeNormURL"], path.lstrip("/"))
        status = requests.get(url, timeout=REQUEST_TIMEOUT).status_code
        if status == 404 or status >= 500:
            not_served.append(f"{path} (HTTP {status})")
    if not_served == ["/get_allowed_conflations (HTTP 500)"]:
        raise KnownElasticsearchDiscrepancy(
            f"{doc_url} documents /get_allowed_conflations, which returns HTTP 500"
        )
    assert (
        not not_served
    ), f"{doc_url} documents paths this deployment does not serve: {truncated_repr(not_served)}"
