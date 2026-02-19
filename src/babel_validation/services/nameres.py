import logging
import time

import requests

cached_nameres_by_url = {}

class CachedNameRes:
    # TODO: actually cache once we've implemented a param-based cache.
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
            raise ValueError(f"queries must be a list when calling normalize_curies({queries}, {params}) on {self}")

        time_started = time.time_ns()
        queries_set = set(queries)
        cached_queries = queries_set & self.cache.keys()
        queries_to_be_queried = queries_set - cached_queries

        # Make query.
        result = {}
        if queries_to_be_queried:
            params['strings'] = list(queries_to_be_queried)

            self.logger.debug(f"Called NameRes {self} with params {params}")
            response = requests.post(self.nameres_url + "bulk-lookup", json=params)
            response.raise_for_status()
            result = response.json()

            for query in queries_to_be_queried:
                self.cache[query] = result.get(query, None)

        for query in cached_queries:
            result[query] = self.cache[query]

        time_taken_sec = (time.time_ns() - time_started) / 1E9
        self.logger.info(f"Looked up {len(queries_to_be_queried)} queries {queries_to_be_queried} (with {len(cached_queries)} queries cached) with params {params} on {self} in {time_taken_sec:.3f}s")

        return result

    def lookup(self, query, **params):
        if query in self.cache:
            return self.cache[query]

        params['string'] = query
        self.logger.debug(f"Querying NameRes with params {params}")

        response = requests.post(self.nameres_url + "lookup", params=params)
        response.raise_for_status()
        result = response.json()

        self.cache[query] = result
        return result

    def delete_query(self, query):
        if query in self.cache:
            del self.cache[query]
