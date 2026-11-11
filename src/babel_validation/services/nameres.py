"""
Cached client for the NameRes ``bulk-lookup`` and ``lookup`` APIs.

Caching model
-------------
Each response is stored under the key
``(endpoint, query, frozenset(params.items()))``.  Entries are never evicted
automatically; call ``invalidate_query()`` to force a fresh lookup for a
specific query string.

``lookup()`` and ``bulk_lookup()`` keep separate entries, because the two
endpoints do not answer the same request the same way, so a result from one is
not a valid answer for the other.  As of NameRes in 2026-11
(``api/server.py``):

- They name the type filter differently -- ``biolink_type`` on ``/lookup``,
  ``biolink_types`` on ``/bulk-lookup`` -- and each silently ignores the other
  name, so the same keyword arguments filter on one endpoint and not the other.
- ``/lookup`` rejects a query shorter than NameRes's minimum length with an
  HTTP 422, where ``/bulk-lookup`` returns an empty list for it.

They used to share one keyspace, on the premise that equal parameters gave
equal hits.  Both differences above broke that, and a ``bulk_lookup()`` could
then hand unfiltered hits, or an ``[]`` in place of an error, to a later
``lookup()``.  Do not merge them again.

Cache-warming pattern
---------------------
When you need to look up many query strings for the same logical task, call
``bulk_lookup()`` once with the full list.  That issues a single HTTP POST to
the ``bulk-lookup`` endpoint and populates the cache.  Subsequent
``bulk_lookup()`` calls for any subset of those queries are served from cache.
This does not warm ``lookup()``, for the reasons above.

Endpoint differences
--------------------
``bulk_lookup()`` targets ``/bulk-lookup`` and sends the query list as a JSON
body.  ``lookup()`` targets the separate ``/lookup`` endpoint and sends its
parameters as a URL query string.  Their return types differ accordingly --
a ``{query: hits}`` mapping against a bare list of hits.
"""

import logging
import time
from typing import Protocol

import requests

cached_nameres_by_url = {}

# The first element of every cache key, recording which endpoint produced the entry.
LOOKUP = "lookup"
BULK_LOOKUP = "bulk-lookup"


class NameResService(Protocol):
    """Interface that callers should depend on.

    Type parameters against this Protocol rather than ``CachedNameRes``
    directly so that a future drop-in library replacement requires no caller
    changes.
    """

    def bulk_lookup(self, queries: list[str], **params) -> dict[str, dict]: ...
    def lookup(self, query: str, **params) -> list[dict]: ...
    def invalidate_query(self, query: str) -> None: ...


class CachedNameRes:
    def __init__(self, nameres_url: str):
        self.nameres_url = nameres_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNameRes({self.nameres_url})"

    @staticmethod
    def from_url(nameres_url: str) -> "CachedNameRes":
        """Return the singleton ``CachedNameRes`` for *nameres_url*.

        The singleton ensures that cache entries accumulated during one part of
        a test run are reused by later parts that share the same URL.  Prefer
        this over direct construction unless you explicitly want a fresh cache.
        """
        if nameres_url not in cached_nameres_by_url:
            cached_nameres_by_url[nameres_url] = CachedNameRes(nameres_url)
        return cached_nameres_by_url[nameres_url]

    def bulk_lookup(self, queries: list[str], **params) -> dict[str, dict]:
        """Look up *queries* in bulk, returning a ``{query: result}`` mapping.

        Already-cached queries are served from the cache; the remainder are
        fetched from NameRes in a single HTTP POST to ``bulk-lookup``.
        The response is merged with the cached results before returning.

        *queries* must be a non-empty list — the NameRes API rejects empty
        requests, so this method raises ``ValueError`` immediately.

        Use this as the cache-warming call; subsequent ``bulk_lookup()`` calls
        for any subset of these queries will be free.
        """
        if not queries:
            raise ValueError(f"queries must not be empty when calling bulk_lookup({queries}, {params}) on {self}")
        if not isinstance(queries, list):
            raise ValueError(f"queries must be a list when calling bulk_lookup({queries}, {params}) on {self}")

        time_started = time.time_ns()
        params_key = frozenset(params.items())
        queries_set = set(queries)
        cached_queries = {q for q in queries_set if (BULK_LOOKUP, q, params_key) in self.cache}
        queries_to_be_queried = queries_set - cached_queries

        result = {}
        if queries_to_be_queried:
            api_params = dict(params)
            api_params["strings"] = list(queries_to_be_queried)

            self.logger.debug("Called NameRes %s with params %s", self, api_params)
            response = requests.post(self.nameres_url + "bulk-lookup", json=api_params, timeout=30)
            response.raise_for_status()
            result = response.json()

            # /bulk-lookup answers every string it is sent, so a missing one means a response we
            # do not understand. Leave it out of the result and the cache rather than caching
            # None, which would be handed back forever as if it were a list of hits.
            missing = queries_to_be_queried - result.keys()
            if missing:
                self.logger.warning(
                    "NameRes %s returned no result for %d of %d strings, e.g. %r; not caching them",
                    self,
                    len(missing),
                    len(queries_to_be_queried),
                    sorted(missing)[0][:100],
                )
            for query in queries_to_be_queried - missing:
                self.cache[(BULK_LOOKUP, query, params_key)] = result[query]

        for query in cached_queries:
            result[query] = self.cache[(BULK_LOOKUP, query, params_key)]

        time_taken_sec = (time.time_ns() - time_started) / 1e9
        self.logger.info(
            "Looked up %d queries (with %d cached) with params %s on %s in %.3fs",
            len(queries_to_be_queried),
            len(cached_queries),
            params,
            self,
            time_taken_sec,
        )

        return result

    def lookup(self, query: str, **params) -> list[dict]:
        """Look up a single *query* string via the NameRes ``/lookup`` endpoint.

        This targets a different endpoint from ``bulk_lookup()`` — parameters
        are sent as URL query string fields, and the response is a list of
        result dicts rather than a mapping.  Results are cached per
        ``(query, params)`` combination, separately from ``bulk_lookup()``'s:
        the two endpoints can answer the same parameters differently (see the
        module docstring), so neither serves the other from cache.

        This method does NOT delegate to ``bulk_lookup()``, for the same
        reason.  To cache-warm for single lookups, call this method upfront.
        """
        cache_key = (LOOKUP, query, frozenset(params.items()))
        if cache_key in self.cache:
            return self.cache[cache_key]

        api_params = dict(params)
        api_params["string"] = query
        self.logger.debug("Querying NameRes with params %s", api_params)

        response = requests.post(self.nameres_url + "lookup", params=api_params, timeout=30)
        response.raise_for_status()
        result = response.json()

        self.cache[cache_key] = result
        return result

    def invalidate_query(self, query: str) -> None:
        """Remove all cached results for *query* (across every param variant and both endpoints).

        The next call to ``lookup()`` or ``bulk_lookup()`` for this query will
        issue a fresh HTTP request.
        """
        keys_to_delete = [k for k in self.cache if k[1] == query]
        for k in keys_to_delete:
            del self.cache[k]
