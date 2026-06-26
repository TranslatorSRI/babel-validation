"""
Cached client for the NameRes ``bulk-lookup`` and ``lookup`` APIs.

Caching model
-------------
Each response is stored under the key ``(query, frozenset(params.items()))``.
Entries are never evicted automatically; call ``delete_query()`` to force
a fresh lookup for a specific query string.

Cache-warming pattern
---------------------
When you need to look up many query strings for the same logical task, call
``bulk_lookup()`` once with the full list.  That issues a single HTTP POST to
the ``bulk-lookup`` endpoint and populates the cache.  Subsequent
``bulk_lookup()`` calls for any subset of those queries are served from cache.

Endpoint differences
--------------------
``bulk_lookup()`` targets ``/bulk-lookup`` and sends the query list as a JSON
body.  ``lookup()`` targets the separate ``/lookup`` endpoint and sends its
parameters as a URL query string.  These are distinct API endpoints with
different response shapes; ``lookup()`` does NOT delegate to ``bulk_lookup()``.
"""

import logging
import time

import requests

cached_nameres_by_url = {}

class CachedNameRes:
    def __init__(self, nameres_url: str):
        self.nameres_url = nameres_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNameRes({self.nameres_url})"

    @staticmethod
    def from_url(nameres_url: str) -> 'CachedNameRes':
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
        cached_queries = {q for q in queries_set if (q, params_key) in self.cache}
        queries_to_be_queried = queries_set - cached_queries

        result = {}
        if queries_to_be_queried:
            api_params = dict(params)
            api_params['strings'] = list(queries_to_be_queried)

            self.logger.debug("Called NameRes %s with params %s", self, api_params)
            response = requests.post(self.nameres_url + "bulk-lookup", json=api_params, timeout=30)
            response.raise_for_status()
            result = response.json()

            for query in queries_to_be_queried:
                self.cache[(query, params_key)] = result.get(query, None)

        for query in cached_queries:
            result[query] = self.cache[(query, params_key)]

        time_taken_sec = (time.time_ns() - time_started) / 1E9
        self.logger.info("Looked up %d queries (with %d cached) with params %s on %s in %.3fs",
                         len(queries_to_be_queried), len(cached_queries), params, self, time_taken_sec)

        return result

    def lookup(self, query, **params):
        """Look up a single *query* string via the NameRes ``/lookup`` endpoint.

        This targets a different endpoint from ``bulk_lookup()`` — parameters
        are sent as URL query string fields, and the response is a list of
        result dicts rather than a mapping.  Results are cached per
        ``(query, params)`` combination.

        This method does NOT delegate to ``bulk_lookup()``.  To cache-warm for
        single lookups, call this method (or ``bulk_lookup()``) upfront.
        """
        cache_key = (query, frozenset(params.items()))
        if cache_key in self.cache:
            return self.cache[cache_key]

        api_params = dict(params)
        api_params['string'] = query
        self.logger.debug("Querying NameRes with params %s", api_params)

        response = requests.post(self.nameres_url + "lookup", params=api_params, timeout=30)
        response.raise_for_status()
        result = response.json()

        self.cache[cache_key] = result
        return result

    def delete_query(self, query):
        """Remove all cached results for *query* (across every param variant).

        The next call to ``lookup()`` or ``bulk_lookup()`` for this query will
        issue a fresh HTTP request.
        """
        keys_to_delete = [k for k in self.cache if k[0] == query]
        for k in keys_to_delete:
            del self.cache[k]
