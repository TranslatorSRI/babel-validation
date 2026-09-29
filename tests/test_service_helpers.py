"""A malformed OpenAPI document must produce a readable failure, not a raw exception.

Everything checked here comes off the network, so the only thing that can be assumed
about the parsed document is that it is JSON: `info`, `x-translator` and `infores` can
each be missing, or present as something other than what they should be. Reaching into
any of them without checking raises AttributeError or TypeError, which is exactly the
unreadable failure these helpers exist to replace.
"""

import pytest

from tests._service_helpers import (
    MAX_KEYS_LISTED,
    MAX_REPR_LENGTH,
    assert_backend,
    assert_x_translator,
    nameres_version_shortfall,
    openapi_url,
    parse_version,
    truncated_keys_repr,
    truncated_repr,
)

pytestmark = pytest.mark.unit

INFORES = 'infores:sri-node-normalizer'
URL = 'https://example.org/openapi.json'


def valid_document():
    return {'info': {'title': 'NodeNorm', 'x-translator': {'infores': INFORES}}}


def test_a_valid_document_passes():
    assert_x_translator(URL, valid_document(), INFORES)


@pytest.mark.parametrize('document, expected_message', [
    # A document that isn't an object at all: FastAPI would never return this, but a
    # proxy or an error page rendered as JSON might.
    ([], 'did not return a JSON object'),
    ('not a document', 'did not return a JSON object'),
    # An info that is absent, or present as something we can't look inside.
    ({'openapi': '3.1.0'}, 'has no info block'),
    ({'info': None}, 'has an info that is not a JSON object'),
    ({'info': 'NodeNorm'}, 'has an info that is not a JSON object'),
    # The case this all started from: FastAPI's default document, which has an info
    # but no x-translator in it.
    ({'info': {'title': 'FastAPI', 'version': '0.1.0'}}, 'has no info.x-translator block'),
    # An x-translator that is present but malformed reports as malformed, not as
    # absent — "missing it altogether" points at the wrong diagnosis here.
    ({'info': {'x-translator': []}}, 'has an info.x-translator that is not a JSON object'),
    ({'info': {'x-translator': 'infores:sri-node-normalizer'}},
     'has an info.x-translator that is not a JSON object'),
    # The right shape, the wrong service.
    ({'info': {'x-translator': {'infores': 'infores:sri-name-resolver'}}},
     'declares info.x-translator.infores'),
    ({'info': {'x-translator': {}}}, 'declares info.x-translator.infores'),
])
def test_a_malformed_document_fails_with_a_readable_message(document, expected_message):
    with pytest.raises(AssertionError) as excinfo:
        assert_x_translator(URL, document, INFORES)

    assert expected_message in str(excinfo.value)


def test_the_failure_message_is_bounded_however_large_the_document():
    """The message is kept in pytest's report, so a service cannot be allowed to choose its size."""
    document = {'info': {str(i): 'x' * 10_000 for i in range(1000)}}

    with pytest.raises(AssertionError) as excinfo:
        assert_x_translator(URL, document, INFORES)

    message = str(excinfo.value)
    assert 'has no info.x-translator block' in message
    assert len(message) < 1000
    assert '(+980 more)' in message


def test_the_failure_message_escapes_control_characters():
    """repr() is the whole defence for text that reaches a terminal or a log line."""
    document = {'info': {'x-translator': {'infores': '\x1b[2Jinfores:not-this-one‮'}}}

    with pytest.raises(AssertionError) as excinfo:
        assert_x_translator(URL, document, INFORES)

    message = str(excinfo.value)
    assert '\x1b' not in message
    assert '‮' not in message
    assert '\\x1b[2Jinfores:not-this-one\\u202e' in message


def test_truncated_repr_keeps_short_values_intact():
    assert truncated_repr('short') == "'short'"


def test_truncated_repr_caps_long_values():
    text = truncated_repr('x' * 10_000)

    assert len(text) < MAX_REPR_LENGTH + 100
    assert 'truncated to' in text


def test_truncated_keys_repr_caps_the_number_of_keys():
    text = truncated_keys_repr({str(i): i for i in range(MAX_KEYS_LISTED + 5)})

    assert '(+5 more)' in text


class TestOpenAPIURL:
    """The path to the document is per-target: the -es deployments don't serve it at the root."""

    def test_it_defaults_to_the_fastapi_location(self):
        target_info = {'NodeNormURL': 'https://nodenorm.example.org/'}

        assert openapi_url(target_info, 'NodeNormURL', 'NodeNormOpenAPIPath') == \
            'https://nodenorm.example.org/openapi.json'

    def test_it_uses_the_configured_path(self):
        target_info = {
            'NodeNormURL': 'https://nodenorm-es.example.org/',
            'NodeNormOpenAPIPath': 'webapp/openapi.json',
        }

        assert openapi_url(target_info, 'NodeNormURL', 'NodeNormOpenAPIPath') == \
            'https://nodenorm-es.example.org/webapp/openapi.json'


class TestBackend:
    """Which backend a target talks to is configuration, and /status is how we hold it to that."""

    def test_the_configured_backend_passes(self):
        assert_backend(URL, {'status': 'running', 'backend': 'elasticsearch'}, 'elasticsearch')

    def test_the_other_backend_fails(self):
        with pytest.raises(AssertionError) as excinfo:
            assert_backend(URL, {'status': 'running', 'backend': 'redis'}, 'elasticsearch')

        message = str(excinfo.value)
        assert "reports backend 'redis'" in message
        assert "configured as 'elasticsearch'" in message

    def test_a_status_that_is_not_an_object_fails_readably(self):
        with pytest.raises(AssertionError) as excinfo:
            assert_backend(URL, ['running'], 'redis')

        assert 'did not return a JSON object' in str(excinfo.value)

    def test_a_backend_that_is_not_a_string_is_reported_safely(self):
        with pytest.raises(AssertionError) as excinfo:
            assert_backend(URL, {'backend': {'name': '\x1b[2Jredis'}}, 'redis')

        message = str(excinfo.value)
        assert '\x1b' not in message
        assert '\\x1b[2Jredis' in message


@pytest.mark.parametrize("text, expected", [
    ('v1.7.1', (1, 7, 1)),
    ('1.7.1', (1, 7, 1)),
    (' v1.7.1 ', (1, 7, 1)),
    ('v1.7', (1, 7)),
    ('v1.7.1-rc1', (1, 7, 1)),
    ('v10.0.2', (10, 0, 2)),
])
def test_parse_version_reads_release_tags(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize("text", [None, 17, '', 'v', 'latest', 'v1..7', '1.7.1.dev0', 'v1.7.1 extra', '1' * 100])
def test_parse_version_rejects_anything_else(text):
    assert parse_version(text) is None


STATUS_URL = 'https://example.org/status'
FEATURE = 'exact matching'


def test_a_new_enough_nameres_is_not_skipped():
    assert nameres_version_shortfall(STATUS_URL, {'nameres_version': 'v1.7.1'}, (1, 7, 1), FEATURE) is None
    assert nameres_version_shortfall(STATUS_URL, {'nameres_version': 'v1.10.0'}, (1, 7, 1), FEATURE) is None


def test_an_older_nameres_is_skipped_with_its_version_named():
    reason = nameres_version_shortfall(STATUS_URL, {'nameres_version': 'v1.7.0'}, (1, 7, 1), FEATURE)
    assert "'v1.7.0'" in reason
    assert 'v1.7.1 or later' in reason
    assert FEATURE in reason


def test_a_nameres_without_a_version_is_skipped():
    # Older releases, and the Elasticsearch-backed NameLookup, do not report one.
    reason = nameres_version_shortfall(STATUS_URL, {'status': 'ok'}, (1, 7, 1), FEATURE)
    assert 'does not report a nameres_version' in reason


@pytest.mark.parametrize("status_json", [['not', 'an', 'object'], {'nameres_version': 'latest'}])
def test_a_malformed_status_fails_rather_than_skips(status_json):
    with pytest.raises(AssertionError):
        nameres_version_shortfall(STATUS_URL, status_json, (1, 7, 1), FEATURE)


def test_an_unparseable_version_is_escaped_in_the_failure():
    with pytest.raises(AssertionError) as excinfo:
        nameres_version_shortfall(STATUS_URL, {'nameres_version': '\x1b[31mv1'}, (1, 7, 1), FEATURE)
    assert '\x1b' not in str(excinfo.value)
    assert '\\x1b' in str(excinfo.value)
