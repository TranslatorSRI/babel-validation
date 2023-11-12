#
# Tests for the NameRes API
# These tests are intended to ensure that all the API endpoints on NameRes are working as intended.
#
import urllib.parse

import requests


def test_openapi_json(target_info):
    nameres_url = target_info['NameResURL']

    url = urllib.parse.urljoin(nameres_url, 'openapi.json')
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    openapi_json = response.json()
    assert openapi_json['info']['x-translator']['infores'] == 'infores:sri-name-resolver'