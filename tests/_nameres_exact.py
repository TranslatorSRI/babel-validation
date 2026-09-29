"""Shared checks for NameRes exact mode (the `exact` parameter added in NameRes v1.7.1).

With `exact` set, /lookup and /bulk-lookup skip the tokenized search and return only
concepts whose *whole* preferred name (`label`), a whole synonym (`synonyms`), or
either (`any`) equals the search string, case-insensitively and after leading and
trailing whitespace is stripped. Results are then sorted by clique size rather than
by score. See https://github.com/NCATSTranslator/NameResolution/blob/main/documentation/API.md#exact-matching

Used by both the hand-written exact-mode tests and the Google Sheet ones, so that both
hold every response to the same definition of "exact".
"""

from tests._service_helpers import require_nameres_version, truncated_repr

EXACT_MODES = ('label', 'synonyms', 'any')
EXACT_MINIMUM_VERSION = (1, 7, 1)


def require_exact_mode(target_info):
    """Skip the calling test unless this target's NameRes supports `exact`."""
    require_nameres_version(target_info, EXACT_MINIMUM_VERSION, "the `exact` search parameter")


def _normalize(name):
    # NameRes strips the query and lowercases both sides (the *_exactish fields are a
    # KeywordTokenizer plus a LowerCaseFilter). Stripping the stored names too would
    # hide a server that had started trimming them, so only the query is stripped.
    return name.lower()


def exact_match_problems(query, mode, results):
    """
    List the ways an exact-mode response breaks the definition of exact matching.

    :param query: The search string, as sent.
    :param mode: The `exact` mode it was sent with: one of EXACT_MODES.
    :param results: The parsed list of results for that query.
    :return: A list of human-readable problems; empty if the response is correct.
    """
    if mode not in EXACT_MODES:
        raise ValueError(f"Unknown exact mode {mode!r}")
    if not isinstance(results, list):
        return [f"expected a list of results, got {truncated_repr(results)}"]

    wanted = _normalize(query.strip())
    problems = []
    if not all(isinstance(result, dict) for result in results):
        return [f"expected a list of result objects, got {truncated_repr(results)}"]

    for index, result in enumerate(results):
        label = result.get('label') or ''
        synonyms = result.get('synonyms') or []
        label_matches = _normalize(label) == wanted
        synonym_matches = any(_normalize(synonym) == wanted for synonym in synonyms)

        if mode == 'label':
            matches = label_matches
        elif mode == 'synonyms':
            matches = synonym_matches
        else:
            matches = label_matches or synonym_matches

        if not matches:
            problems.append(
                f"result {index} ({truncated_repr(result.get('curie'))}, label {truncated_repr(label)}) "
                f"has no {'preferred name' if mode == 'label' else 'name'} equal to {truncated_repr(query)}"
            )

    # With nothing to score, exact mode sorts by clique size, largest first.
    counts = [result.get('clique_identifier_count', 0) for result in results]
    for index in range(1, len(counts)):
        if counts[index] > counts[index - 1]:
            problems.append(
                f"results are not sorted by clique_identifier_count: result {index} has "
                f"{truncated_repr(counts[index])}, after {truncated_repr(counts[index - 1])}"
            )
            break

    return problems


def assert_exact_results(description, query, mode, results):
    """
    Assert that an exact-mode response only contains exact matches, in clique-size order.

    :param description: What was asked, for the failure message (e.g. the URL).
    :param query: The search string, as sent.
    :param mode: The `exact` mode it was sent with.
    :param results: The parsed list of results for that query.
    """
    problems = exact_match_problems(query, mode, results)
    assert not problems, (
        f"{description} with exact={mode} for {truncated_repr(query)} returned results that are not exact "
        f"matches: " + "; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "")
    )
