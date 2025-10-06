#
# Tests for the NodeNorm API setid methods.
# These tests are intended to ensure that all the API setid endpoints on NodeNorm are working as intended.
# Copied and modified from https://github.com/NCATSTranslator/NodeNormalization/blob/d697af9f2ff99f16ebfe0c9a8e375b9d440c8f98/tests/test_setid.py
# Note that since this depends on normalization, these examples may need to be updated if any of the CURIEs we
# reference here have different preferred identifiers in a future release.
#

import pytest
import requests

@pytest.fixture
def nodenorm_url(target_info):
    return target_info['NodeNormURL']

def test_setid_empty(nodenorm_url):
    """
    Make sure we get a sensible response if we call setid without any parameters.
    """
    response = requests.get(nodenorm_url + "get_setid")
    result = response.json()

    # Check for NodeNorm ES:
    if response.status_code == 400:
        assert result == {
            'code': 400,
            'error': 'Bad Request',
            'success': False,
        }
        return

    assert result == {
        "detail":
            [
                {
                    "loc": ["query", "curie"],
                    "msg": "ensure this value has at least 1 items",
                    "type": "value_error.list.min_items",
                    "ctx": { "limit_value": 1 }
                }
            ]
    }


def test_setid_incorrect_conflation(nodenorm_url):
    """
    Make sure we get a sensible response if we call setid without any parameters.
    """
    response = requests.get(nodenorm_url + "get_setid", params={
        'curie': ['DOID:3812', 'MONDO:0005002', 'MONDO:0005003'],
        'conflation': ['GeneProtein', 'DrugChemic']
    })
    result = response.json()
    assert "only 'GeneProtein' and 'DrugChemical' are allowed" in result['error']
    assert result['setid'] is None


def test_setid_basic(nodenorm_url):
    """
    Some basic tests to make sure normalization works as expected.
    """
    expected_setids = [
        {
            'curie': ['DOID:3812', 'MONDO:0005002', 'MONDO:0005003', 'PUBCHEM.COMPOUND:10129877', ''],
            'conflation': ['GeneProtein'],
            'curies': ['DOID:3812', 'MONDO:0005002', 'MONDO:0005003', 'PUBCHEM.COMPOUND:10129877', ''],
            'normalized_curies': ['', 'DOID:3812', 'MONDO:0005002', 'MONDO:0005003', 'UNII:63M8RYN44N'],
            'normalized_string': '||DOID:3812||MONDO:0005002||MONDO:0005003||UNII:63M8RYN44N',
            'setid': 'uuid:4a69cea4-e267-5cb5-bf69-66cc19da65ca'
        },
        {
            'curie': ['DOID:3812', 'MONDO:0005002', 'MONDO:0005003', 'PUBCHEM.COMPOUND:10129877', ''],
            'conflation': ['GeneProtein', 'DrugChemical'],
            'curies': ['DOID:3812', 'MONDO:0005002', 'MONDO:0005003', 'PUBCHEM.COMPOUND:10129877', ''],
            'normalized_curies': ['', 'CHEBI:15377', 'DOID:3812', 'MONDO:0005002', 'MONDO:0005003'],
            'normalized_string': '||CHEBI:15377||DOID:3812||MONDO:0005002||MONDO:0005003',
            'setid': 'uuid:7403b843-5adb-563b-a321-876cb2088f2b'
        },
        {
            'curie': ['!#lk1l4', '09s90ma!:391nasa01AAa', 10.31, 9018, -913],
            'conflation': ['GeneProtein', 'DrugChemical'],
            'curies': ['!#lk1l4', '09s90ma!:391nasa01AAa', '10.31', '9018', '-913'],
            'normalized_curies': ['!#lk1l4', '-913', '09s90ma!:391nasa01AAa', '10.31', '9018'],
            'normalized_string': '!#lk1l4||-913||09s90ma!:391nasa01AAa||10.31||9018',
            'setid': 'uuid:2fe78021-4a98-53cc-b911-a55962575095'
        }
    ]

    for expected_setid in expected_setids:
        response = requests.get(nodenorm_url + "get_setid", params={
            'curie': expected_setid['curie'],
            'conflation': expected_setid['conflation'],
        })
        result = response.json()
        assert result['curies'] == expected_setid['curies']
        assert result['error'] is None
        assert result['normalized_curies'] == expected_setid['normalized_curies']
        assert result['normalized_string'] == expected_setid['normalized_string']
        assert result['setid'] == expected_setid['setid']

    # Test all of them at once using the 'POST' interface.
    setid_query = [{'curies': e['curie'], 'conflations': e['conflation']} for e in expected_setids]
    response = requests.post(nodenorm_url + "get_setid", json=setid_query)
    results = response.json()
    for index, result in enumerate(results):
        expected_setid = expected_setids[index]

        assert result['error'] is None
        assert result['normalized_curies'] == expected_setid['normalized_curies']
        assert result['normalized_string'] == expected_setid['normalized_string']
        assert result['setid'] == expected_setid['setid']


def test_setid_long(nodenorm_url):
    """
    Some basic tests to make sure normalization of long lists of setid.
    """
    # Generate up to a hundred rubbish IDs (between RUBBISH:10000 and RUBBISH:99999).
    # rubbish_ids = [f'RUBBISH:{random.randint(10000, 99999)}' for _ in range(100)]
    rubbish_ids = ["RUBBISH:47029", "RUBBISH:11782", "RUBBISH:19841", "RUBBISH:74772", "RUBBISH:50159", "RUBBISH:72510", "RUBBISH:71390", "RUBBISH:93274", "RUBBISH:54177", "RUBBISH:11018", "RUBBISH:75654", "RUBBISH:82342", "RUBBISH:58851", "RUBBISH:37847", "RUBBISH:39315", "RUBBISH:95403", "RUBBISH:87724", "RUBBISH:76080", "RUBBISH:62554", "RUBBISH:11207", "RUBBISH:24788", "RUBBISH:97930", "RUBBISH:98994", "RUBBISH:10111", "RUBBISH:46486", "RUBBISH:42114", "RUBBISH:97410", "RUBBISH:71911", "RUBBISH:10444", "RUBBISH:71057", "RUBBISH:16589", "RUBBISH:79128", "RUBBISH:32169", "RUBBISH:76813", "RUBBISH:13051", "RUBBISH:75665", "RUBBISH:33554", "RUBBISH:73285", "RUBBISH:79791", "RUBBISH:99397", "RUBBISH:36508", "RUBBISH:81324", "RUBBISH:27651", "RUBBISH:60525", "RUBBISH:13237", "RUBBISH:21080", "RUBBISH:21874", "RUBBISH:94750", "RUBBISH:95994", "RUBBISH:35060", "RUBBISH:15816", "RUBBISH:65196", "RUBBISH:74530", "RUBBISH:61006", "RUBBISH:97287", "RUBBISH:29972", "RUBBISH:36823", "RUBBISH:31799", "RUBBISH:68589", "RUBBISH:68594", "RUBBISH:63257", "RUBBISH:81351", "RUBBISH:38292", "RUBBISH:84666", "RUBBISH:50607", "RUBBISH:52926", "RUBBISH:48712", "RUBBISH:14093", "RUBBISH:88546", "RUBBISH:29904", "RUBBISH:75316", "RUBBISH:68679", "RUBBISH:99691", "RUBBISH:59711", "RUBBISH:57302", "RUBBISH:18425", "RUBBISH:71720", "RUBBISH:37939", "RUBBISH:23971", "RUBBISH:64822", "RUBBISH:69092", "RUBBISH:73348", "RUBBISH:56239", "RUBBISH:17439", "RUBBISH:80884", "RUBBISH:36822", "RUBBISH:11304", "RUBBISH:18228", "RUBBISH:59644", "RUBBISH:15815", "RUBBISH:93668", "RUBBISH:84725", "RUBBISH:40687", "RUBBISH:95196", "RUBBISH:12572", "RUBBISH:98753", "RUBBISH:52910", "RUBBISH:27338", "RUBBISH:28744", "RUBBISH:70919"]
    response = requests.get(nodenorm_url + "get_setid", params={
        'curie': rubbish_ids
    })
    result = response.json()
    assert result['curies'] == rubbish_ids
    assert result['normalized_curies'] == [
        'RUBBISH:10111',
        'RUBBISH:10444',
        'RUBBISH:11018',
        'RUBBISH:11207',
        'RUBBISH:11304',
        'RUBBISH:11782',
        'RUBBISH:12572',
        'RUBBISH:13051',
        'RUBBISH:13237',
        'RUBBISH:14093',
        'RUBBISH:15815',
        'RUBBISH:15816',
        'RUBBISH:16589',
        'RUBBISH:17439',
        'RUBBISH:18228',
        'RUBBISH:18425',
        'RUBBISH:19841',
        'RUBBISH:21080',
        'RUBBISH:21874',
        'RUBBISH:23971',
        'RUBBISH:24788',
        'RUBBISH:27338',
        'RUBBISH:27651',
        'RUBBISH:28744',
        'RUBBISH:29904',
        'RUBBISH:29972',
        'RUBBISH:31799',
        'RUBBISH:32169',
        'RUBBISH:33554',
        'RUBBISH:35060',
        'RUBBISH:36508',
        'RUBBISH:36822',
        'RUBBISH:36823',
        'RUBBISH:37847',
        'RUBBISH:37939',
        'RUBBISH:38292',
        'RUBBISH:39315',
        'RUBBISH:40687',
        'RUBBISH:42114',
        'RUBBISH:46486',
        'RUBBISH:47029',
        'RUBBISH:48712',
        'RUBBISH:50159',
        'RUBBISH:50607',
        'RUBBISH:52910',
        'RUBBISH:52926',
        'RUBBISH:54177',
        'RUBBISH:56239',
        'RUBBISH:57302',
        'RUBBISH:58851',
        'RUBBISH:59644',
        'RUBBISH:59711',
        'RUBBISH:60525',
        'RUBBISH:61006',
        'RUBBISH:62554',
        'RUBBISH:63257',
        'RUBBISH:64822',
        'RUBBISH:65196',
        'RUBBISH:68589',
        'RUBBISH:68594',
        'RUBBISH:68679',
        'RUBBISH:69092',
        'RUBBISH:70919',
        'RUBBISH:71057',
        'RUBBISH:71390',
        'RUBBISH:71720',
        'RUBBISH:71911',
        'RUBBISH:72510',
        'RUBBISH:73285',
        'RUBBISH:73348',
        'RUBBISH:74530',
        'RUBBISH:74772',
        'RUBBISH:75316',
        'RUBBISH:75654',
        'RUBBISH:75665',
        'RUBBISH:76080',
        'RUBBISH:76813',
        'RUBBISH:79128',
        'RUBBISH:79791',
        'RUBBISH:80884',
        'RUBBISH:81324',
        'RUBBISH:81351',
        'RUBBISH:82342',
        'RUBBISH:84666',
        'RUBBISH:84725',
        'RUBBISH:87724',
        'RUBBISH:88546',
        'RUBBISH:93274',
        'RUBBISH:93668',
        'RUBBISH:94750',
        'RUBBISH:95196',
        'RUBBISH:95403',
        'RUBBISH:95994',
        'RUBBISH:97287',
        'RUBBISH:97410',
        'RUBBISH:97930',
        'RUBBISH:98753',
        'RUBBISH:98994',
        'RUBBISH:99397',
        'RUBBISH:99691'
    ]
    assert result['normalized_string'] == 'RUBBISH:10111||RUBBISH:10444||RUBBISH:11018||RUBBISH:11207||RUBBISH:11304||RUBBISH:11782||RUBBISH:12572||RUBBISH:13051||RUBBISH:13237||RUBBISH:14093||RUBBISH:15815||RUBBISH:15816||RUBBISH:16589||RUBBISH:17439||RUBBISH:18228||RUBBISH:18425||RUBBISH:19841||RUBBISH:21080||RUBBISH:21874||RUBBISH:23971||RUBBISH:24788||RUBBISH:27338||RUBBISH:27651||RUBBISH:28744||RUBBISH:29904||RUBBISH:29972||RUBBISH:31799||RUBBISH:32169||RUBBISH:33554||RUBBISH:35060||RUBBISH:36508||RUBBISH:36822||RUBBISH:36823||RUBBISH:37847||RUBBISH:37939||RUBBISH:38292||RUBBISH:39315||RUBBISH:40687||RUBBISH:42114||RUBBISH:46486||RUBBISH:47029||RUBBISH:48712||RUBBISH:50159||RUBBISH:50607||RUBBISH:52910||RUBBISH:52926||RUBBISH:54177||RUBBISH:56239||RUBBISH:57302||RUBBISH:58851||RUBBISH:59644||RUBBISH:59711||RUBBISH:60525||RUBBISH:61006||RUBBISH:62554||RUBBISH:63257||RUBBISH:64822||RUBBISH:65196||RUBBISH:68589||RUBBISH:68594||RUBBISH:68679||RUBBISH:69092||RUBBISH:70919||RUBBISH:71057||RUBBISH:71390||RUBBISH:71720||RUBBISH:71911||RUBBISH:72510||RUBBISH:73285||RUBBISH:73348||RUBBISH:74530||RUBBISH:74772||RUBBISH:75316||RUBBISH:75654||RUBBISH:75665||RUBBISH:76080||RUBBISH:76813||RUBBISH:79128||RUBBISH:79791||RUBBISH:80884||RUBBISH:81324||RUBBISH:81351||RUBBISH:82342||RUBBISH:84666||RUBBISH:84725||RUBBISH:87724||RUBBISH:88546||RUBBISH:93274||RUBBISH:93668||RUBBISH:94750||RUBBISH:95196||RUBBISH:95403||RUBBISH:95994||RUBBISH:97287||RUBBISH:97410||RUBBISH:97930||RUBBISH:98753||RUBBISH:98994||RUBBISH:99397||RUBBISH:99691'
    assert result['setid'] == 'uuid:c81cd168-996a-5ca7-8107-2c82c36232fe'
