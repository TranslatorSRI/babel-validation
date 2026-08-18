"""Offline tests for the caching in CachedNodeNorm and CachedNameRes.

These are the only tests in this repository that exercise
``babel_validation.services``; every other test calls NodeNorm and NameRes
through ``requests`` directly. Since the caching is what those classes exist
for -- and a cache that silently stops caching just makes a run slower rather
than failing it -- the behaviour is pinned here rather than left to be noticed
in production.

``requests.post`` is replaced by a recorder, so nothing here touches the
network.
"""

import pytest

from babel_validation.services import nameres as nameres_module
from babel_validation.services import nodenorm as nodenorm_module
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class Recorder:
    """Stand-in for ``requests.post`` that records calls and replays a payload.

    ``payload`` may be a value or a callable taking the keyword arguments of
    the request, which lets a fake response echo back whatever was asked for.
    """

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        payload = self._payload(kwargs) if callable(self._payload) else self._payload
        return FakeResponse(payload)

    @property
    def call_count(self):
        return len(self.calls)


def echo_curies(kwargs):
    """A NodeNorm response resolving every requested CURIE to a stub record."""
    return {curie: {"id": {"identifier": curie}} for curie in kwargs["json"]["curies"]}


def echo_strings(kwargs):
    """A NameRes bulk-lookup response returning one stub hit per requested string."""
    return {string: [{"curie": f"CURIE:{string}"}] for string in kwargs["json"]["strings"]}


@pytest.fixture
def nodenorm(monkeypatch):
    """A CachedNodeNorm whose HTTP calls are recorded instead of sent."""
    recorder = Recorder(echo_curies)
    monkeypatch.setattr(nodenorm_module.requests, "post", recorder)
    return CachedNodeNorm("https://nodenorm.example/"), recorder


@pytest.fixture
def nameres(monkeypatch):
    """A CachedNameRes whose HTTP calls are recorded instead of sent."""
    recorder = Recorder(echo_strings)
    monkeypatch.setattr(nameres_module.requests, "post", recorder)
    return CachedNameRes("https://nameres.example/"), recorder


# --- CachedNodeNorm -------------------------------------------------------


def test_repeated_normalize_curies_makes_one_request(nodenorm):
    nn, recorder = nodenorm

    first = nn.normalize_curies(["MONDO:0005148", "HP:0000118"])
    second = nn.normalize_curies(["MONDO:0005148", "HP:0000118"])

    assert first == second
    assert recorder.call_count == 1, "the second call should have been served entirely from cache"


def test_normalize_curies_requests_only_the_uncached_remainder(nodenorm):
    nn, recorder = nodenorm

    nn.normalize_curies(["MONDO:0005148"])
    result = nn.normalize_curies(["MONDO:0005148", "HP:0000118"])

    assert recorder.call_count == 2
    assert recorder.calls[1][1]["json"]["curies"] == ["HP:0000118"], "cached CURIE was re-requested"
    # The merged result still covers both, not just the CURIE that was fetched.
    assert set(result) == {"MONDO:0005148", "HP:0000118"}


def test_normalize_curie_is_free_after_warming(nodenorm):
    nn, recorder = nodenorm

    nn.normalize_curies(["MONDO:0005148", "HP:0000118"])
    result = nn.normalize_curie("HP:0000118")

    assert result == {"id": {"identifier": "HP:0000118"}}
    assert recorder.call_count == 1, "this is the cache-warming pattern the module docstring promises"


def test_params_are_part_of_the_cache_key(nodenorm):
    nn, recorder = nodenorm

    nn.normalize_curie("MONDO:0005148")
    nn.normalize_curie("MONDO:0005148", conflate=True)

    assert recorder.call_count == 2, "a different params combination must not reuse the cached response"


def test_unresolvable_curie_caches_none(nodenorm, monkeypatch):
    nn, _ = nodenorm
    # NodeNorm omits CURIEs it cannot resolve rather than returning null for them.
    recorder = Recorder({})
    monkeypatch.setattr(nodenorm_module.requests, "post", recorder)

    assert nn.normalize_curie("NOSUCH:1") is None
    assert nn.normalize_curie("NOSUCH:1") is None
    assert recorder.call_count == 1, "a negative result should be cached too, not retried every time"


def test_invalidate_curie_clears_every_param_variant(nodenorm):
    nn, recorder = nodenorm

    nn.normalize_curie("MONDO:0005148")
    nn.normalize_curie("MONDO:0005148", conflate=True)
    nn.invalidate_curie("MONDO:0005148")
    nn.normalize_curie("MONDO:0005148")
    nn.normalize_curie("MONDO:0005148", conflate=True)

    assert recorder.call_count == 4, "invalidation must drop the entries for all params, not just the default"


def test_invalidate_curie_leaves_other_curies_cached(nodenorm):
    nn, recorder = nodenorm

    nn.normalize_curies(["MONDO:0005148", "HP:0000118"])
    nn.invalidate_curie("MONDO:0005148")
    nn.normalize_curie("HP:0000118")

    assert recorder.call_count == 1, "invalidating one CURIE should not flush the whole cache"


@pytest.mark.parametrize("bad", [[], "MONDO:0005148", ("MONDO:0005148",)])
def test_normalize_curies_rejects_bad_input(nodenorm, bad):
    nn, recorder = nodenorm

    # NodeNorm rejects an empty request, and a bare string would be sent as a
    # list of characters, so both are refused before any HTTP call is made.
    with pytest.raises(ValueError):
        nn.normalize_curies(bad)
    assert recorder.call_count == 0


def test_from_url_returns_a_shared_instance():
    url = "https://nodenorm-singleton.example/"
    assert CachedNodeNorm.from_url(url) is CachedNodeNorm.from_url(url)
    assert CachedNodeNorm.from_url(url) is not CachedNodeNorm(url)


# --- CachedNameRes --------------------------------------------------------


def test_repeated_bulk_lookup_makes_one_request(nameres):
    nr, recorder = nameres

    first = nr.bulk_lookup(["diabetes", "asthma"])
    second = nr.bulk_lookup(["diabetes", "asthma"])

    assert first == second
    assert recorder.call_count == 1


def test_bulk_lookup_requests_only_the_uncached_remainder(nameres):
    nr, recorder = nameres

    nr.bulk_lookup(["diabetes"])
    result = nr.bulk_lookup(["diabetes", "asthma"])

    assert recorder.call_count == 2
    assert recorder.calls[1][1]["json"]["strings"] == ["asthma"]
    assert set(result) == {"diabetes", "asthma"}


def test_bulk_lookup_posts_strings_to_the_bulk_endpoint(nameres):
    nr, recorder = nameres

    nr.bulk_lookup(["diabetes"], limit=5)

    url, kwargs = recorder.calls[0]
    assert url == "https://nameres.example/bulk-lookup"
    # bulk-lookup takes a JSON body keyed `strings`; `lookup` differs on both counts.
    assert kwargs["json"] == {"limit": 5, "strings": ["diabetes"]}
    assert "params" not in kwargs


def test_lookup_sends_a_query_string_to_the_lookup_endpoint(monkeypatch):
    recorder = Recorder([{"curie": "MONDO:0005148"}])
    monkeypatch.setattr(nameres_module.requests, "post", recorder)
    nr = CachedNameRes("https://nameres.example/")

    result = nr.lookup("diabetes", limit=5)

    url, kwargs = recorder.calls[0]
    assert url == "https://nameres.example/lookup"
    assert kwargs["params"] == {"limit": 5, "string": "diabetes"}
    assert "json" not in kwargs
    # A list of hits, not the {string: hits} mapping bulk_lookup returns.
    assert result == [{"curie": "MONDO:0005148"}]

    assert nr.lookup("diabetes", limit=5) == result
    assert recorder.call_count == 1


def test_lookup_and_bulk_lookup_share_one_cache_namespace(monkeypatch):
    """The shared keyspace is deliberate; this pins it so a change is noticed.

    Both methods key the cache on ``(query, params)`` with no note of which
    endpoint produced the entry, so a `lookup()` result is handed straight back
    to a later `bulk_lookup()` for the same query and params, with no request
    made. That is correct as long as the two endpoints stay interchangeable for
    equal parameters -- `/lookup` returns a list of hits, `/bulk-lookup` returns
    that same list under the string it was asked about -- which is the premise
    the module docstring now records.

    If NameRes ever makes them disagree, this test fails, which is the point.
    """
    recorder = Recorder([{"curie": "MONDO:0005148"}])
    monkeypatch.setattr(nameres_module.requests, "post", recorder)
    nr = CachedNameRes("https://nameres.example/")

    from_lookup = nr.lookup("diabetes")
    from_bulk = nr.bulk_lookup(["diabetes"])

    assert recorder.call_count == 1, "bulk_lookup reused the /lookup cache entry"
    assert from_bulk == {"diabetes": from_lookup}


def test_invalidate_query_clears_both_endpoints(monkeypatch):
    recorder = Recorder([{"curie": "MONDO:0005148"}])
    monkeypatch.setattr(nameres_module.requests, "post", recorder)
    nr = CachedNameRes("https://nameres.example/")

    nr.lookup("diabetes")
    nr.invalidate_query("diabetes")
    nr.lookup("diabetes")

    assert recorder.call_count == 2


@pytest.mark.parametrize("bad", [[], "diabetes", ("diabetes",)])
def test_bulk_lookup_rejects_bad_input(nameres, bad):
    nr, recorder = nameres

    with pytest.raises(ValueError):
        nr.bulk_lookup(bad)
    assert recorder.call_count == 0


def test_from_url_returns_a_shared_instance_for_nameres():
    url = "https://nameres-singleton.example/"
    assert CachedNameRes.from_url(url) is CachedNameRes.from_url(url)
