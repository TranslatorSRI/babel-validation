"""Shared pytest helpers for deferring network-backed parametrization.

Several test modules build their parametrization from network sources (the
Google Sheet, GitHub issues) at collection time. pytest only applies ``-m``
marker deselection *after* test generation, so a run like ``pytest -m unit``
would still pay for those fetches before discarding the tests. Evaluating the
marker expression ourselves lets us skip the fetch when the test won't run.
"""


def deselected_by_markexpr(metafunc) -> bool:
    """True if an active ``-m`` marker expression would deselect this test.

    Returns False (i.e. "keep it") whenever there is no ``-m`` filter, the
    internal expression API is unavailable, or the expression can't be parsed —
    so this never suppresses a test that pytest would otherwise run.
    """
    markexpr = metafunc.config.getoption("markexpr")
    if not markexpr:
        return False
    try:
        from _pytest.mark.expression import Expression
    except ImportError:
        # Internal API moved; fall back to the (network-using) default.
        return False
    own_markers = {m.name for m in metafunc.definition.iter_markers()}
    try:
        return not Expression.compile(markexpr).evaluate(lambda name: name in own_markers)
    except Exception:
        # Unparseable expression — let pytest handle it; don't suppress tests.
        return False
