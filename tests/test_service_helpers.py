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
    assert_x_translator,
    openapi_url,
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
