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

from dataclasses import dataclass

from src.babel_validation.core import cache_dir
from src.babel_validation.tools.generate_report import (
    OUTCOME_SEVERITY,
    annotate_result,
    classify_record,
    issue_url,
    parse_nodeid,
    validate_source_url,
)

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


# The user properties a Google Sheet test records (tests/*/test_*_from_gsheet.py), with the
# label each gets in the "Google Sheet row" section of a failure report.
SHEET_ROW_FIELDS = {
    "category": "Category",
    "source": "Source",
    "source_url": "Source URL",
    "query_id": "Query ID",
    "query_label": "Query label",
}


def sheet_row_section(user_properties, allowlist=()):
    """
    The text of a "Google Sheet row" report section for a failing sheet test, or None for any
    other test. Its assertion messages do include the row, but as one long TestRow repr, so
    which kind of test it was and where it came from were hard to find.

    The values are sheet cells, which anyone with edit access can write, and the section is
    printed to the terminal and into public Actions logs: each is !r-escaped and truncated.
    The Source URL is free text and could link anywhere (another Google Sheet, whose URL is
    its capability), so like the end-of-run summary's links (annotate_result) it is shown
    only if it points into a repository on the Repositories allowlist.

    :param allowlist: The lower-cased org/repo names in targets.ini's Repositories list.
    """
    props = dict(user_properties)
    if "category" not in props:
        return None
    url = props.get("source_url")
    if url and not validate_source_url(url, allowlist):
        props["source_url"] = None
        hidden = "(not shown: not a link into a Repositories repo in targets.ini)"
    else:
        hidden = None
    width = max(len(label) for label in SHEET_ROW_FIELDS.values())
    return "\n".join(
        f"{label + ':':<{width + 1}} "
        + (hidden if key == "source_url" and hidden else _sheet_cell(props.get(key)))
        for key, label in SHEET_ROW_FIELDS.items()
    )


def _sheet_cell(value, limit=200):
    # Truncated before repr(), so a huge cell is never escaped in full, and again after it,
    # because repr() can turn one character into ten ('\U000e0001').
    text = repr(str(value or "")[:limit])
    return text if len(text) <= limit else text[: limit - 1] + "…"


# Services, with the targets.ini key holding each one's URL. They come first in the summary,
# each under its own heading; every other directory under tests/ (or file directly in it) is
# listed under "Other".
SUMMARY_SERVICES = {"nodenorm": ("NodeNorm", "NodeNormURL"), "nameres": ("NameRes", "NameResURL")}
SUMMARY_DEFAULT_MAX_LISTED = 50
SUMMARY_MAX_PER_GROUP = 10
SUMMARY_MAX_FILES = 5

# Outcomes that are a problem on the target (a strict XPASS fails the run), and outcomes left out
# of the pass rate: expected failures and skips aren't results about the service.
PROBLEM_OUTCOMES = ("failed", "error", "xpassed")
NOT_COUNTED = ("xfailed", "skipped")

# Terminal markup, as pytest's TerminalWriter names it ("light" is faint/dim).
BOLD = {"bold": True}
DIM = {"light": True}
OUTCOME_MARKUP = {
    "passed": {"green": True},
    "failed": {"red": True},
    "error": {"red": True},
    "xpassed": {"yellow": True},
    "xfailed": DIM,
    "skipped": DIM,
}


def pass_rate(passed, counted):
    """A whole-number percentage that is 100% only if everything passed and 0% only if nothing
    did. Plain rounding (`:.0%`) printed 199 of 200 as "(100%)" right next to "1 failed", so a
    glance at the rate missed the regression; a single pass in 300 likewise read as "(0%)"."""
    if passed == counted:
        return "100%"
    if passed == 0:
        return "0%"
    return f"{min(max(100 * passed // counted, 1), 99)}%"


@dataclass
class RunSummary:
    """What build_summary() counted, for render_summary() to lay out."""

    targets: list
    categories_include: set
    categories_exclude: set
    # (component, target) -> {outcome: number of tests}; target is "?" for untargeted tests.
    counts: dict
    # (component, target) -> the URL that was tested, for services only.
    urls: dict
    # component -> {file path: number of distinct tests in it}.
    files: dict
    # test key -> {target: outcome}; target is "?" for untargeted tests.
    outcomes: dict
    # (test key, target) -> the node ID, to list a failing test in a form pytest can rerun.
    nodeids: dict
    # test key -> an allowlisted link to what the test is about (its GitHub issue, say).
    links: dict


def build_summary(
    records, targets, target_sections, categories_include, categories_exclude, allowlist=()
):
    """
    Count the run for the end-of-run summary printed by pytest_terminal_summary in
    tests/conftest.py.

    `records` are the raw per-phase dicts that conftest's pytest_runtest_logreport builds (the
    same shape --report-jsonl writes), so outcomes are worked out exactly as the dashboard's
    report generator does it: the worst outcome per test wins. A test's target is the "target"
    property conftest's pytest_itemcollected records, not a guess from the node ID, which would
    take a unit test parametrized with '2026sep24-dev' or 'prod' for a test of that target;
    parse_nodeid is only used to strip the target from the key of tests that have one.

    :param targets: The target names this run tested, in --target order.
    :param target_sections: Mapping of target name to its targets.ini section (for the URLs).
    :param allowlist: The lower-cased org/repo names in targets.ini's Repositories list. Only
        links into these are shown (see _link).
    """
    outcomes = {}  # test key without target -> {target: worst outcome across its phases}
    nodeids = {}
    rests = {}  # test key -> its parametrize ID without the target
    props = {}  # test key -> its user properties, merged across phases and targets
    for record in records:
        record_props = record.get("props") or {}
        target = record_props.get("target")
        if target is None:
            key, target, rest = record["id"].removeprefix("tests/"), "?", ""
        else:
            key, _, rest = parse_nodeid(record["id"], [target])
        nodeids[(key, target)] = record["id"]
        rests[key] = rest
        props.setdefault(key, {}).update(record_props)
        outcome = classify_record(record)
        by_target = outcomes.setdefault(key, {})
        if OUTCOME_SEVERITY[outcome] >= OUTCOME_SEVERITY[by_target.get(target, "passed")]:
            by_target[target] = outcome

    counts = {}
    files = {}  # component -> {file path: number of distinct tests in it}
    for key, by_target in outcomes.items():
        # The directory under tests/, or the file name for a file directly in tests/. Only the
        # path before "::" counts, since a parameter can itself contain a slash.
        path = key.split("::")[0]
        component = path.split("/")[0]
        paths = files.setdefault(component, {})
        paths[path] = paths.get(path, 0) + 1
        for target, outcome in by_target.items():
            counts.setdefault((component, target), dict.fromkeys(OUTCOME_SEVERITY, 0))[outcome] += 1

    urls = {}
    for component, target in counts:
        if component in SUMMARY_SERVICES and target in target_sections:
            url = target_sections[target].get(SUMMARY_SERVICES[component][1])
            if url:
                urls[(component, target)] = url

    return RunSummary(
        targets=list(targets),
        categories_include=set(categories_include),
        categories_exclude=set(categories_exclude),
        counts=counts,
        urls=urls,
        files=files,
        outcomes=outcomes,
        nodeids=nodeids,
        links={
            key: link
            for key in props
            if (link := _link(key, rests[key], props[key], allowlist))
        },
    )


def _link(key, rest, props, allowlist):
    """
    A link to what a test is about, to list beside it when it fails: the GitHub issue a GitHub
    issue test came from, or the Source URL of a Google Sheet row. Both are untrusted, and this
    summary is printed into public Actions logs, so the dashboard's annotate_result decides:
    the same allowlist checks, and nothing for the blocklist tests.
    """
    annotation = annotate_result(key, rest, props, allowlist)
    if "issue" in annotation:
        return issue_url(annotation["issue"])
    return annotation.get("source_url")


def _counted(c):
    return sum(n for outcome, n in c.items() if outcome not in NOT_COUNTED)


def _has_problem(c):
    return any(c[o] for o in PROBLEM_OUTCOMES)


def _rate_cell(c):
    counted = _counted(c)
    if not counted:
        return "—", DIM
    # Coloured as the worst outcome it counts: red for a failure or error, yellow for an xpass.
    worst = max((o for o, n in c.items() if n and o not in NOT_COUNTED), key=OUTCOME_SEVERITY.get)
    return pass_rate(c["passed"], counted), OUTCOME_MARKUP[worst]


def _count_cell(n, markup):
    # Zeroes are a dim dot, so the counts that matter stand out.
    return (str(n), markup) if n else ("·", DIM)


# The table's columns after "rate" and "passed": (heading, outcome counted), with a divider
# (no outcome) before the outcomes left out of the rate.
_COUNT_COLUMNS = [
    ("failed", "failed"),
    ("error", "error"),
    ("xpass", "xpassed"),
    ("│", None),
    ("xfail", "xfailed"),
    ("skip", "skipped"),
]
_COLUMNS = ["rate", "passed"] + [heading for heading, _ in _COUNT_COLUMNS]


def _row_cells(c):
    return [_rate_cell(c), (f"{c['passed']}/{_counted(c)}", {})] + [
        _count_cell(c[outcome], OUTCOME_MARKUP[outcome]) if outcome else ("│", DIM)
        for _, outcome in _COUNT_COLUMNS
    ]


def _target_order(summary):
    return list(summary.targets) + ["?"]


def _other_components(summary):
    """The tests/ directories (or files directly in it) that are not services, for "Other"."""
    return sorted({comp for comp, _ in summary.counts if comp not in SUMMARY_SERVICES})


def _table(summary):
    """The pass-rate table: services first, then everything else under "Other"."""
    # Rows are ("heading", indent, label, markup, note) or ("row", indent, label, cells, tail),
    # where tail is a service row's URL or an untargeted group's file list, after the columns.
    rows = []

    def add_target_rows(component, indent):
        for target in _target_order(summary):
            c = summary.counts.get((component, target))
            if c is None:
                continue
            label = "—" if target == "?" else target
            rows.append(("row", indent, label, _row_cells(c), summary.urls.get((component, target))))

    for component, (name, _) in SUMMARY_SERVICES.items():
        if any(comp == component for comp, _ in summary.counts):
            rows.append(("heading", 0, name, BOLD, None))
            add_target_rows(component, 1)

    others = _other_components(summary)
    if others:
        rows.append(("heading", 0, "Other", BOLD, None))
        for component in others:
            # Which files the group holds, so tests that belong to no service are easy to see.
            files = summary.files.get(component, {})
            note = None
            if not (len(files) == 1 and component in files):
                listed = sorted(files.items())
                note = ", ".join(
                    f"{path.split('/', 1)[-1]}: {n}" for path, n in listed[:SUMMARY_MAX_FILES]
                )
                if len(listed) > SUMMARY_MAX_FILES:
                    note += f", … {len(listed) - SUMMARY_MAX_FILES} more files"
            if [t for comp, t in summary.counts if comp == component] == ["?"]:
                # Only untargeted tests (unit tests, say): one row, named after the group.
                c = summary.counts[(component, "?")]
                rows.append(("row", 1, component, _row_cells(c), f"({note})" if note else None))
            else:
                rows.append(("heading", 1, component, {}, note))
                add_target_rows(component, 2)

    data_rows = [r for r in rows if r[0] == "row"]
    label_width = max([2 * r[1] + len(r[2]) for r in data_rows] + [0])
    widths = [
        max([len(heading)] + [len(r[3][i][0]) for r in data_rows])
        for i, heading in enumerate(_COLUMNS)
    ]

    def cells_line(label_segment, cells, tail):
        segments = [label_segment]
        for (text, markup), width in zip(cells, widths):
            segments.append(("  ", {}))
            segments.append((text.rjust(width), markup))
        if tail:
            segments.append(("  " + tail, DIM))
        return segments

    header = cells_line((" " * label_width, {}), [(h, BOLD) for h in _COLUMNS], None)
    if summary.urls:
        header.append(("  URL", BOLD))
    lines = [header]
    for row in rows:
        if row[0] == "heading":
            _, indent, label, markup, note = row
            segments = [("  " * indent + label, markup)]
            if note:
                segments.append((f"  ({note})", DIM))
            lines.append(segments)
        else:
            _, indent, label, cells, tail = row
            lines.append(cells_line((("  " * indent + label).ljust(label_width), {}), cells, tail))
    return lines


def _result_line(summary):
    """One verdict per service and for everything else, e.g. "NodeNorm ✗ ci, test · NameRes ✓"."""
    groups = [(name, [comp]) for comp, (name, _) in SUMMARY_SERVICES.items()]
    groups.append(("Other", _other_components(summary)))
    segments = [("Result:", BOLD)]
    for name, components in groups:
        cells = {k: c for k, c in summary.counts.items() if k[0] in components}
        if not cells:
            continue
        segments.append((" " if len(segments) == 1 else " · ", {}))
        failing = []
        for target in _target_order(summary):
            if any(_has_problem(c) for (_, t), c in cells.items() if t == target):
                failing.append("untargeted" if target == "?" else target)
        if failing:
            segments.append((f"{name} ✗ {', '.join(failing)}", {"red": True}))
        elif any(_counted(c) for c in cells.values()):
            segments.append((f"{name} ✓", {"green": True}))
        else:
            segments.append((f"{name} — nothing passed or failed", DIM))
    return segments


def _listed_groups(summary):
    """
    The tests to list after the table, grouped by their pattern of outcomes across targets:
    every test that failed, errored or xpassed anywhere, and every test whose outcome differs
    between targets.
    """
    order = _target_order(summary)
    groups = {}
    for key, outcomes in summary.outcomes.items():
        # Only targets the test actually ran on are compared: a test missing from one target
        # (because it wasn't parametrized there) isn't reported as a difference.
        differs = len(set(outcomes.values())) > 1
        if not differs and not any(o in PROBLEM_OUTCOMES for o in outcomes.values()):
            continue
        pattern = tuple((t, outcomes[t]) for t in order if t in outcomes)
        groups.setdefault(pattern, []).append(key)

    def tier(pattern):
        seen = {outcome for _, outcome in pattern}
        if seen & set(PROBLEM_OUTCOMES):
            return 0
        if "xfailed" in seen:
            return 1
        return 2  # Differs only by a skip, typically require_babel_release.

    def in_target_order(pattern):
        # Not the pattern itself, whose target names would sort alphabetically: ties follow
        # --target order, like the table and everything else in the summary.
        return tuple((order.index(target), outcome) for target, outcome in pattern)

    return sorted(
        groups.items(), key=lambda g: (tier(g[0]), -len(g[1]), in_target_order(g[0]))
    )


def _pattern_heading(pattern):
    """E.g. "failed on dev; passed on prod", with each outcome coloured."""
    by_outcome = {}
    for target, outcome in pattern:
        by_outcome.setdefault(outcome, []).append(target)
    segments = []
    for outcome, targets in by_outcome.items():
        if segments:
            segments.append(("; ", {}))
        segments.append((outcome, OUTCOME_MARKUP[outcome]))
        named = [t for t in targets if t != "?"]
        if named:
            segments.append((f" on {', '.join(named)}", {}))
    return segments


def _example_nodeid(summary, key, pattern):
    """The node ID to show for a test: from the first target where it went wrong, if any."""
    for wanted in (PROBLEM_OUTCOMES, NOT_COUNTED):
        for target, outcome in pattern:
            if outcome in wanted:
                return summary.nodeids[(key, target)]
    return summary.nodeids[(key, pattern[0][0])]


def _listed_tests(summary, max_listed):
    groups = _listed_groups(summary)
    total = sum(len(keys) for _, keys in groups)
    title = "Failures and differences between targets" if len(summary.targets) > 1 else "Failures"
    lines = [[(f"{title}: {total}", BOLD)]]
    unlimited = max_listed < 0
    remaining = total if unlimited else max_listed
    per_group = total if unlimited else SUMMARY_MAX_PER_GROUP
    listed = 0
    for pattern, keys in groups:
        lines.append([("  ", {})] + _pattern_heading(pattern) + [(f" ({len(keys)}):", {})])
        shown = min(len(keys), per_group, remaining)
        remaining -= shown
        listed += shown
        for key in sorted(keys)[:shown]:
            # The full node ID, so it can be found in the log above or rerun with pytest; !r,
            # because it carries parametrize IDs built from sheet rows and issue bodies.
            line = [(f"    - {_example_nodeid(summary, key, pattern)!r}", {})]
            if key in summary.links:
                # Printed as it is, so it stays clickable: annotate_result's checks only pass
                # URLs of printable, non-whitespace characters.
                line.append((f" ({summary.links[key]})", {}))
            lines.append(line)
        if 0 < shown < len(keys):
            lines.append([(f"    … and {len(keys) - shown} more", DIM)])
    if listed < total:
        lines.append([(f"  (--summary-max-listed -1 lists all {total})", DIM)])
    return lines


def render_summary(summary, max_listed=SUMMARY_DEFAULT_MAX_LISTED):
    """
    Lay out a RunSummary as lines of (text, markup) segments, where markup is a dict of
    pytest TerminalWriter markup ({"red": True}). conftest writes each segment with
    terminalreporter.write(), which drops the colour for --color=no, NO_COLOR and a
    non-terminal, so nothing here depends on whether colour is on.

    :param max_listed: How many failing or differing tests to list in all; 0 lists only the
        groups' headings, and a negative number lists every one.
    """
    include = ", ".join(sorted(summary.categories_include)) or "all"
    exclude = ", ".join(sorted(summary.categories_exclude)) or "none"
    lines = [
        [("Targets: ", BOLD), (", ".join(summary.targets), {})],
        [("Sheet categories: ", BOLD), (f"{include} · excluded: {exclude}", {})],
        _result_line(summary),
        [],
    ]
    lines.extend(_table(summary))
    lines.append([])
    lines.extend(_listed_tests(summary, max_listed))
    return lines


def plain_text(lines):
    """The rendered summary without markup: one string per line."""
    return ["".join(text for text, _ in line) for line in lines]
