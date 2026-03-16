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
        # TODO: eventually we'll need some way to cache the parameters along with the curie.
        if not curies:
            raise ValueError(f"curies must not be empty when calling normalize_curies({curies}, {params}) on {self}")
        if not isinstance(curies, list):
            raise ValueError(f"curies must be a list when calling normalize_curies({curies}, {params}) on {self}")

        time_started = time.time_ns()
        curies_set = set(curies)
        cached_curies = curies_set & self.cache.keys()
        curies_to_be_queried = curies_set - cached_curies

        # Make query.
        result = {}
        if curies_to_be_queried:
            params['curies'] = list(curies_to_be_queried)

            self.logger.debug(f"Called NodeNorm {self} with params {params}")
            response = requests.post(self.nodenorm_url + "get_normalized_nodes", json=params)
            response.raise_for_status()
            result = response.json()

            for curie in curies_to_be_queried:
                self.cache[curie] = result.get(curie, None)

        for curie in cached_curies:
            result[curie] = self.cache[curie]

        time_taken_sec = (time.time_ns() - time_started) / 1E9
        self.logger.info(f"Normalizing {len(curies_to_be_queried)} CURIEs {curies_to_be_queried} (with {len(cached_curies)} CURIEs cached) with params {params} on {self} in {time_taken_sec:.3f}s")

        return result

    def normalize_curie(self, curie, **params):
        if curie in self.cache:
            return self.cache[curie]
        return self.normalize_curies([curie], **params)[curie]

    def clear_curie(self, curie):
        # This will be needed if you need to call a CURIE with different parameters.
        if curie in self.cache:
            del self.cache[curie]
