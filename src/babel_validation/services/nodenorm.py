"""
Cached client for the NodeNorm ``get_normalized_nodes`` API.

Caching model
-------------
Each response is stored under the key ``(curie, frozenset(params.items()))``.
Entries are never evicted automatically; call ``invalidate_curie()`` to force
a fresh lookup for a specific identifier.

Cache-warming pattern
---------------------
When you need to normalize many CURIEs for the same logical task (e.g. all
CURIEs referenced in a GitHub issue), call ``normalize_curies()`` once with
the full list.  That issues a single HTTP request and populates the cache.
Subsequent ``normalize_curie()`` calls for any of those identifiers return
immediately from cache — no additional HTTP traffic.
"""

import logging
import time
from typing import Protocol

import requests

cached_node_norms_by_url = {}


class NodeNormService(Protocol):
    """Interface that callers should depend on.

    Type parameters against this Protocol rather than ``CachedNodeNorm``
    directly so that a future drop-in library replacement requires no caller
    changes.
    """

    def normalize_curies(self, curies: list[str], **params) -> dict[str, dict | None]: ...
    def normalize_curie(self, curie: str, **params) -> dict | None: ...
    def invalidate_curie(self, curie: str) -> None: ...


class CachedNodeNorm:
    def __init__(self, nodenorm_url: str):
        self.nodenorm_url = nodenorm_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNodeNorm({self.nodenorm_url})"

    @staticmethod
    def from_url(nodenorm_url: str) -> 'CachedNodeNorm':
        """Return the singleton ``CachedNodeNorm`` for *nodenorm_url*.

        The singleton ensures that cache entries accumulated during one part of
        a test run are reused by later parts that share the same URL.  Prefer
        this over direct construction unless you explicitly want a fresh cache.
        """
        if nodenorm_url not in cached_node_norms_by_url:
            cached_node_norms_by_url[nodenorm_url] = CachedNodeNorm(nodenorm_url)
        return cached_node_norms_by_url[nodenorm_url]

    def normalize_curies(self, curies: list[str], **params) -> dict[str, dict | None]:
        """Normalize *curies* in bulk, returning a ``{curie: result}`` mapping.

        Already-cached CURIEs are served from the cache; the remainder are
        fetched from NodeNorm in a single HTTP POST to ``get_normalized_nodes``.
        The response is merged with the cached results before returning.

        *curies* must be a non-empty list — the NodeNorm API rejects empty
        requests, so this method raises ``ValueError`` immediately.

        Values in the returned dict are ``None`` for CURIEs NodeNorm could not
        resolve.  Use this as the cache-warming call; subsequent
        ``normalize_curie()`` calls for these identifiers will be free.
        """
        if not curies:
            raise ValueError(f"curies must not be empty when calling normalize_curies({curies}, {params}) on {self}")
        if not isinstance(curies, list):
            raise ValueError(f"curies must be a list when calling normalize_curies({curies}, {params}) on {self}")

        time_started = time.time_ns()
        params_key = frozenset(params.items())
        curies_set = set(curies)
        cached_curies = {c for c in curies_set if (c, params_key) in self.cache}
        curies_to_be_queried = curies_set - cached_curies

        # Make query.
        result = {}
        if curies_to_be_queried:
            api_params = dict(params)
            api_params['curies'] = list(curies_to_be_queried)

            self.logger.debug("Called NodeNorm %s with params %s", self, api_params)
            response = requests.post(self.nodenorm_url + "get_normalized_nodes", json=api_params, timeout=30)
            response.raise_for_status()
            result = response.json()

            for curie in curies_to_be_queried:
                self.cache[(curie, params_key)] = result.get(curie, None)

        for curie in cached_curies:
            result[curie] = self.cache[(curie, params_key)]

        time_taken_sec = (time.time_ns() - time_started) / 1E9
        self.logger.info("Normalizing %d CURIEs %s (with %d CURIEs cached) with params %s on %s in %.3fs",
                         len(curies_to_be_queried), curies_to_be_queried, len(cached_curies), params, self, time_taken_sec)

        return result

    def normalize_curie(self, curie: str, **params) -> dict | None:
        """Normalize a single *curie*, returning the NodeNorm result or ``None``.

        Checks the cache first; on a miss, delegates to ``normalize_curies()``
        (one HTTP call) and returns the result.  If you expect to normalize many
        CURIEs, call ``normalize_curies()`` upfront so this method never makes
        an HTTP call.

        Uses ``.get()`` rather than direct indexing so that a NodeNorm response
        that silently omits a requested CURIE returns ``None`` instead of
        raising ``KeyError``.
        """
        cache_key = (curie, frozenset(params.items()))
        if cache_key in self.cache:
            return self.cache[cache_key]
        return self.normalize_curies([curie], **params).get(curie)

    def invalidate_curie(self, curie: str) -> None:
        """Remove all cached results for *curie* (across every param variant).

        The next call to ``normalize_curie()`` or ``normalize_curies()`` for
        this identifier will issue a fresh HTTP request.
        """
        keys_to_delete = [k for k in self.cache if k[0] == curie]
        for k in keys_to_delete:
            del self.cache[k]
