"""Shared pytest helpers for deferring network-backed parametrization.

Several test modules build their parametrization from network sources (the
Google Sheet, GitHub issues) at collection time. pytest only applies ``-m``
marker deselection *after* test generation, so a run like ``pytest -m unit``
would still pay for those fetches before discarding the tests. Evaluating the
marker expression ourselves lets us skip the fetch when the test won't run.

Also holds the GitHub issue cache paths, so the root conftest can clear the
cache without duplicating the filenames the github_issues conftest owns, and
the end-of-run summary that the root conftest prints.
"""

from src.babel_validation.core import cache_dir
from src.babel_validation.tools.generate_report import OUTCOME_SEVERITY, classify_record, parse_nodeid

# IDs of issues carrying BabelTest assertions, shared across xdist workers.
GITHUB_ISSUES_CACHE_FILE = cache_dir() / "issues_cache.json"
GITHUB_ISSUES_LOCK_FILE = GITHUB_ISSUES_CACHE_FILE.with_suffix(".lock")


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


# Components that test one service, with the targets.ini key holding that service's URL.
# Tests elsewhere under tests/ are summarised under their directory name, without a URL.
SUMMARY_COMPONENTS = {"nodenorm": ("NodeNorm", "NodeNormURL"), "nameres": ("NameRes", "NameResURL")}
SUMMARY_MAX_DIFFERENCES = 50


def summarize_run(records, targets, target_sections, categories_include, categories_exclude):
    """
    Lines for the end-of-run summary printed by pytest_terminal_summary in tests/conftest.py.

    `records` are the raw per-phase dicts that conftest's pytest_runtest_logreport builds (the
    same shape --report-jsonl writes), so outcomes and targets are worked out exactly as the
    dashboard's report generator does it: the worst outcome per test wins, and the target is
    parsed out of the node ID.

    :param targets: The target names this run tested, in --target order.
    :param target_sections: Mapping of target name to its targets.ini section (for the URLs).
    """
    # (test key without target, target) -> worst outcome across its phases.
    worst = {}
    for record in records:
        key, target, _ = parse_nodeid(record["id"], targets)
        outcome = classify_record(record)
        if OUTCOME_SEVERITY[outcome] >= OUTCOME_SEVERITY[worst.get((key, target), "passed")]:
            worst[(key, target)] = outcome

    counts = {}  # (component, target) -> {outcome: count}
    by_key = {}  # test key -> {target: outcome}, for targeted tests only
    for (key, target), outcome in worst.items():
        component = key.split("/")[0] if "/" in key else "other"
        component_counts = counts.setdefault((component, target), dict.fromkeys(OUTCOME_SEVERITY, 0))
        component_counts[outcome] += 1
        if target != "?":
            by_key.setdefault(key, {})[target] = outcome

    lines = [
        f"Targets: {', '.join(targets)}; "
        f"included categories: {', '.join(sorted(categories_include)) or 'all'}; "
        f"excluded categories: {', '.join(sorted(categories_exclude)) or 'none'}"
    ]

    component_order = list(SUMMARY_COMPONENTS)
    target_order = list(targets) + ["?"]

    def sort_key(item):
        (component, target), _ = item
        rank = component_order.index(component) if component in component_order else len(component_order)
        return rank, component, target_order.index(target) if target in target_order else len(target_order)

    for (component, target), c in sorted(counts.items(), key=sort_key):
        name, url_key = SUMMARY_COMPONENTS.get(component, (component, None))
        label = name if target == "?" else f"{name} [{target}]"
        url = target_sections[target].get(url_key) if url_key and target in target_sections else None
        if url:
            label += f" {url}"
        run = sum(c.values()) - c["skipped"]
        if run:
            line = f"{label}: passed {c['passed']} of {run} run ({c['passed'] / run:.0%})"
        else:
            line = f"{label}: nothing run"
        others = [f"{c[o]} {o}" for o in ("failed", "error", "xfailed", "xpassed") if c[o]]
        if others:
            line += " — " + ", ".join(others)
        if c["skipped"]:
            line += f"; {c['skipped']} skipped"
        lines.append(line)

    if len(targets) > 1:
        # Only targets the test actually ran on are compared: a test missing from one target
        # (because it wasn't parametrized there) isn't reported as a difference.
        differing = sorted(key for key, outcomes in by_key.items() if len(set(outcomes.values())) > 1)
        lines.append(f"Outcomes differing across targets: {len(differing)}")
        for key in differing[:SUMMARY_MAX_DIFFERENCES]:
            outcomes = by_key[key]
            lines.append(
                f"  {key}: " + ", ".join(f"{t}={outcomes[t]}" for t in targets if t in outcomes)
            )
        if len(differing) > SUMMARY_MAX_DIFFERENCES:
            lines.append(f"  … and {len(differing) - SUMMARY_MAX_DIFFERENCES} more")

    return lines
