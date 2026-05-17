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
        if nameres_url not in cached_nameres_by_url:
            cached_nameres_by_url[nameres_url] = CachedNameRes(nameres_url)
        return cached_nameres_by_url[nameres_url]

    def bulk_lookup(self, queries: list[str], **params) -> dict[str, dict]:
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
        keys_to_delete = [k for k in self.cache if k[0] == query]
        for k in keys_to_delete:
            del self.cache[k]
