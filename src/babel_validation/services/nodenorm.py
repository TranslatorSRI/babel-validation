import logging
import time

import requests

cached_node_norms_by_url = {}

class CachedNodeNorm:
    def __init__(self, nodenorm_url: str):
        self.nodenorm_url = nodenorm_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNodeNorm({self.nodenorm_url})"

    @staticmethod
    def from_url(nodenorm_url: str) -> 'CachedNodeNorm':
        if nodenorm_url not in cached_node_norms_by_url:
            cached_node_norms_by_url[nodenorm_url] = CachedNodeNorm(nodenorm_url)
        return cached_node_norms_by_url[nodenorm_url]

    def normalize_curies(self, curies: list[str], **params) -> dict[str, dict]:
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

    def normalize_curie(self, curie, **params):
        cache_key = (curie, frozenset(params.items()))
        if cache_key in self.cache:
            return self.cache[cache_key]
        return self.normalize_curies([curie], **params)[curie]

    def clear_curie(self, curie):
        keys_to_delete = [k for k in self.cache if k[0] == curie]
        for k in keys_to_delete:
            del self.cache[k]
