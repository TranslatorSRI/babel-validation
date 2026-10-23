"""The exact-mode check must catch a response that is not exact, and pass one that is.

The live tests can only show that a real deployment passes this check; they cannot
show that it would fail on a deployment that got exact mode wrong. These cases stand in
for such a deployment: an old server that ignored `exact` and ran the tokenized search,
a label/synonym mix-up, and results in score order rather than clique-size order.
"""

import pytest

from tests._nameres_exact import exact_match_problems

pytestmark = pytest.mark.unit


def result(curie, label, synonyms, count=1):
    return {'curie': curie, 'label': label, 'synonyms': synonyms, 'clique_identifier_count': count}


PARKINSONIAN = result('MONDO:0021095', 'parkinsonian disorder', ['parkinsonian disorder', 'Parkinsonian Disease'], 10)
WPW = result('MONDO:0008685', 'Wolff-Parkinson-White syndrome', ['Wolff Parkinson White syndrome'], 24)


@pytest.mark.parametrize("query, mode, results", [
    ('parkinsonian disorder', 'label', [PARKINSONIAN]),
    ('  PARKINSONIAN DISORDER  ', 'label', [PARKINSONIAN]),
    ('Parkinsonian Disease', 'synonyms', [PARKINSONIAN]),
    ('parkinsonian disease', 'any', [PARKINSONIAN]),
    ('anything', 'any', []),
    # Equal clique sizes are in order: ties break on the CURIE suffix, which we don't check.
    ('x', 'label', [result('A:2', 'X', [], 3), result('A:1', 'x', [], 3), result('A:3', 'x', [], 1)]),
])
def test_exact_results_pass(query, mode, results):
    assert exact_match_problems(query, mode, results) == []


def test_a_tokenized_match_is_caught():
    # What a pre-v1.7.1 server returns: it ignores `exact` and searches tokens.
    problems = exact_match_problems('parkinson', 'any', [WPW])
    assert len(problems) == 1
    assert 'MONDO:0008685' in problems[0]


def test_a_synonym_only_match_is_not_a_label_match():
    assert exact_match_problems('Parkinsonian Disease', 'label', [PARKINSONIAN])
    assert exact_match_problems('Wolff Parkinson White syndrome', 'label', [WPW])


def test_a_label_only_match_is_not_a_synonym_match():
    assert exact_match_problems('Wolff-Parkinson-White syndrome', 'synonyms', [WPW])
    assert exact_match_problems('Wolff-Parkinson-White syndrome', 'label', [WPW]) == []


def test_internal_whitespace_is_not_normalized():
    assert exact_match_problems('parkinsonian  disorder', 'label', [PARKINSONIAN])


def test_results_out_of_clique_size_order_are_caught():
    problems = exact_match_problems('parkinsonian disorder', 'any', [PARKINSONIAN, dict(PARKINSONIAN, clique_identifier_count=99)])
    assert any('not sorted' in problem for problem in problems)


@pytest.mark.parametrize("results", [{'detail': 'error'}, ['MONDO:0021095']])
def test_a_malformed_response_is_a_problem_not_a_crash(results):
    assert exact_match_problems('parkinsonian disorder', 'any', results)


def test_an_unknown_mode_is_a_programming_error():
    with pytest.raises(ValueError):
        exact_match_problems('parkinsonian disorder', 'exakt', [])
