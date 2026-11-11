#
# generate_report.py - build the dashboard report from raw pytest outcomes.
#
# Reads the JSONL files written by `pytest --report-jsonl` (see tests/conftest.py),
# fetches each target's NodeNorm/NameRes /status endpoint, and writes:
#   - report.json:   the full latest-run report the dashboard renders
#   - history.jsonl: an append-only one-line-per-run summary for trends
#
# Everything in the raw records is untrusted (issue bodies, sheet cells, service
# responses end up in test IDs, properties and failure messages), and report.json
# is published on a public website. So this module is the choke point: all text
# is escaped and truncated here, links are only emitted from validated parts
# (allowlisted org/repo#N issue IDs, allowlisted source URLs), /status responses
# pass through a key whitelist, and blocklist test details are redacted entirely.
#
# Run as:
#   uv run python -m src.babel_validation.tools.generate_report \
#       --raw-dir raw --targets-ini tests/targets.ini \
#       --history-in old_history.jsonl --out-dir website/public/data

import argparse
import configparser
import datetime
import json
import logging
import math
import os
import re
import sys
import time
from pathlib import Path

import requests

from src.babel_validation.core.babel_release import babel_release_date

logger = logging.getLogger(__name__)

# Neither Google Sheet may be referenced in the output: the report must not
# contain the test-case sheet's ID or any link to it (casual observers of the
# public website should not find the sheet), and the blocklist sheet is not
# referenced anywhere in this module at all.

STATUS_TIMEOUT_SECONDS = 30
MAX_MESSAGE_CHARS = 500

# Worst outcome wins when a nodeid has several records (phases, subtests).
OUTCOME_SEVERITY = {
    "passed": 0,
    "skipped": 1,
    "xfailed": 2,
    "xpassed": 3,
    "failed": 4,
    "error": 5,
}

# Outcomes whose messages are worth publishing; passed/xfailed/skipped messages
# are noise and would bloat report.json.
OUTCOMES_WITH_MESSAGES = {"failed", "xpassed", "error"}


def sanitize(text, max_chars=MAX_MESSAGE_CHARS):
    """
    Truncate untrusted text and escape every non-printable character (ANSI
    escapes, C0/C1 controls, bidi overrides, zero-width characters) the way
    repr() would, keeping newlines and tabs readable. Escaping rather than
    stripping keeps hostile content visible instead of silently vanishing.
    """
    if text is None:
        return None
    text = str(text)
    if len(text) > max_chars:
        text = text[:max_chars] + "…[truncated]"
    return "".join(
        ch if ch.isprintable() or ch in "\n\t" else repr(ch)[1:-1] for ch in text
    )


def classify_record(record):
    """Map one raw JSONL record to a dashboard outcome."""
    when = record.get("when")
    outcome = record.get("outcome")
    wasxfail = record.get("wasxfail", False)
    # str(), because read_raw_records validates only that the record is a dict
    # with a string id: a hand-edited or truncated raw file can put anything in
    # msg, and one bad record must cost one record, not the whole report.
    msg = str(record.get("msg") or "")

    if when in ("setup", "teardown"):
        return "error" if outcome == "failed" else "skipped"
    if outcome == "failed":
        # A strict xfail that passed is reported as failed with this prefix.
        if msg.startswith("[XPASS(strict)]"):
            return "xpassed"
        return "failed"
    if outcome == "skipped":
        return "xfailed" if wasxfail else "skipped"
    if outcome == "passed":
        return "xpassed" if wasxfail else "passed"
    logger.warning("Unknown outcome %r in record for %r", outcome, record.get("id"))
    return "error"


def read_targets(targets_ini_path):
    """Return (target names without localhost, repository allowlist, config)."""
    config = configparser.ConfigParser()
    config.read(targets_ini_path, encoding="utf8")
    targets = [section for section in config.sections() if section != "localhost"]
    allowlist = [
        repo.strip().lower()
        for repo in config.defaults().get("repositories", "").splitlines()
        if repo.strip()
    ]
    return targets, allowlist, config


def split_target(param_id, targets):
    """
    Split a parametrize id like 'ci-es-test_row:row=42' or 'test_row:row=42-ci-es'
    into (target, rest). The target's position depends on which
    pytest_generate_tests hook parametrized first, which has changed across
    pytest versions — so accept it at either end. Target names can contain
    hyphens ('ci-es'), so match known names longest-first instead of splitting
    on a hyphen.
    """
    for target in sorted(targets, key=len, reverse=True):
        if param_id == target:
            return target, ""
        if param_id.startswith(target + "-"):
            return target, param_id[len(target) + 1 :]
        if param_id.endswith("-" + target):
            return target, param_id[: -(len(target) + 1)]
    return None, param_id


def parse_nodeid(nodeid, targets):
    """
    Return (result_key, target, rest) for a nodeid. The result key is the
    nodeid with the target stripped from its parametrize id, so the same test
    run against different targets shares a key. Tests without a target (unit
    tests, environment tests) or with an unrecognized target land in the '?'
    bucket rather than crashing the report.
    """
    # Node IDs are rootdir-relative, so `pytest tests --target dev` produces
    # 'tests/nodenorm/...' where `pytest tests/nodenorm/...` produces
    # 'nodenorm/...'. Normalize so result keys (and the kind checks below, and
    # the Dashboard's nodenorm//nameres/ prefix checks) are stable either way.
    nodeid = nodeid.removeprefix("tests/")
    match = re.match(r"^(.*?)\[(.*)\]$", nodeid)
    if not match:
        return nodeid, "?", ""
    base, param_id = match.groups()
    target, rest = split_target(param_id, targets)
    if target is None:
        logger.warning("Could not find a target in node ID %r", nodeid)
        return nodeid, "?", param_id
    key = f"{base}[{rest}]" if rest else base
    return key, target, rest


# Issue ids must look like org/repo#N *and* be in the checked-in allowlist
# before we build a github.com link from them.
ISSUE_ID_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)$")


def validate_issue_id(issue_id, allowlist):
    """Return the validated 'org/repo#N' or None."""
    match = ISSUE_ID_RE.match(issue_id or "")
    if not match:
        return None
    if match.group(1).lower() not in allowlist:
        return None
    return issue_id


def validate_source_url(source_url, allowlist):
    """
    Return source_url only if it is a GitHub URL within an allowlisted
    org/repo; otherwise None. SourceURL is free text from the Google Sheet.
    """
    if not source_url or not source_url.startswith("https://github.com/"):
        return None
    parts = source_url[len("https://github.com/") :].split("/")
    if len(parts) < 2:
        return None
    if f"{parts[0]}/{parts[1]}".lower() not in allowlist:
        return None
    return source_url


def _trimmed_int(value):
    # OverflowError as well as the obvious two: int(float("inf")) raises it, and
    # a /status response is service output we do not control.
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _trimmed_float(value):
    # Non-finite values are dropped rather than kept. Python's json writes them
    # as the bare tokens NaN, Infinity and -Infinity, which are valid Python but
    # not valid JSON: JSON.parse rejects the file, so one service reporting a
    # NaN latency would blank every page of the dashboard rather than one cell.
    try:
        value = round(float(value), 2)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _version_key(version):
    """
    Sort key for a version string such as "9.3.1": its numbers compared as
    numbers, then the whole string to break ties ("9.3.1-SNAPSHOT").
    """
    return [int(n) for n in re.findall(r"[0-9]+", version)], version


def _babel_releases(available):
    """
    The Babel releases in a /status babel.available_versions, oldest first, or
    None if it is in a shape we do not read. NodeNorm ES 1.2.0 sends an object
    keyed by release name (the values are links to each release's README); a
    plain list of names is read the same way. Anything else is logged rather
    than dropped silently, because an empty "Babel releases served" row looks
    exactly like a NodeNorm that serves only its default.
    """
    if isinstance(available, (dict, list)):
        names = {v for v in available if babel_release_date(v)}
        if available and not names:
            logger.warning(
                "babel.available_versions lists %d entries, none a Babel release",
                len(available),
            )
        return sorted(names, key=babel_release_date)
    logger.warning(
        "Unreadable babel.available_versions: a %s, not an object or list",
        type(available).__name__,
    )
    return None


def trim_status(raw, service):
    """
    Whitelist the fields of a NodeNorm or NameRes ("nodenorm" or "nameres")
    /status response. The
    response is untrusted service output: unknown keys are dropped, numbers are
    coerced, strings are escaped and truncated, and babel_version_url is kept
    only if it points into the NCATSTranslator GitHub org.
    """
    if not isinstance(raw, dict):
        return {"error": "InvalidStatus"}
    trimmed = {}
    if "status" in raw:
        trimmed["status"] = sanitize(raw["status"], 50)
    # The service's own release (NodeNorm 2.5.1, NodeNorm ES 1.0.0). NameRes
    # reports its own as nameres_version, below, and from v1.7 lists its Solr
    # core's stats at the top level, where "version" is the index's version
    # counter (68618), not a release. Keyed on the service rather than on the
    # shape of the response, because a NameRes error body need not carry the
    # numDocs that would otherwise give the counter away.
    if service == "nodenorm" and "version" in raw:
        trimmed["version"] = sanitize(raw["version"], 50)
    if "babel_version" in raw:
        trimmed["babel_version"] = sanitize(raw["babel_version"], 50)
    url = raw.get("babel_version_url")
    if isinstance(url, str) and url.lower().startswith(
        "https://github.com/ncatstranslator/"
    ):
        trimmed["babel_version_url"] = sanitize(url, 200)
    # NodeNorm ES from 1.2.0 can serve several Babel releases, chosen per
    # request, and lists them under babel.available_versions. Keep only the
    # names that are real Babel releases, oldest first; a name that passes
    # babel_release_date() is plain ASCII, so it needs no further escaping.
    # Every name is checked before the list is cut to the newest 50, so the
    # releases that matter most cannot be cut off by a long or misordered list.
    babel = raw.get("babel")
    available = babel.get("available_versions") if isinstance(babel, dict) else None
    if available is not None:
        releases = _babel_releases(available)
        if releases is not None:
            trimmed["babel_available_versions"] = releases[-50:]
    biolink = raw.get("biolink_model")
    if isinstance(biolink, dict) and "tag" in biolink:
        trimmed["biolink_version"] = sanitize(biolink["tag"], 100)

    databases = raw.get("databases")
    if isinstance(databases, dict):
        trimmed_dbs = {}
        for name, db in list(databases.items())[:20]:
            if not isinstance(db, dict):
                continue
            entry = {}
            count = _trimmed_int(db.get("count"))
            if count is not None:
                entry["count"] = count
            if "used_memory_rss_human" in db:
                entry["used_memory_rss_human"] = sanitize(
                    db["used_memory_rss_human"], 20
                )
            trimmed_dbs[sanitize(name, 50)] = entry
        trimmed["databases"] = trimmed_dbs

    # NodeNorm ES: its Elasticsearch nodes, reduced to what says whether the
    # cluster is healthy. Every node is counted and read, so a mixed-version
    # cluster (mid rolling upgrade) shows all its versions; only the list of
    # distinct versions is cut short, since that is what reaches the report.
    elasticsearch = raw.get("elasticsearch")
    nodes = elasticsearch.get("nodes") if isinstance(elasticsearch, dict) else None
    if isinstance(nodes, dict):
        node_list = [n for n in nodes.values() if isinstance(n, dict)]
        disk = [_trimmed_float(n.get("disk.used_percent")) for n in node_list]
        disk = [d for d in disk if d is not None]
        # A node can report "version": null (mid-restart, say). sanitize() keeps
        # None as None, and sorting None among strings raises TypeError, which
        # fetch_status would turn into an error for the whole NodeNorm status.
        versions = {
            sanitize(n["version"], 20)
            for n in node_list
            if n.get("version") is not None
        }
        trimmed_es = {"nodes": len(node_list)}
        if versions:
            # Oldest first, compared as numbers: as strings, 8.10.0 sorts before
            # 8.9.0. The cut to five keeps the newest, and is only a bound on
            # hostile input: a real cluster runs one version, or two mid-upgrade.
            trimmed_es["versions"] = sorted(versions, key=_version_key)[-5:]
        if disk:
            trimmed_es["max_disk_used_percent"] = max(disk)
        trimmed["elasticsearch"] = trimmed_es

    # NameRes-only fields.
    if "nameres_version" in raw:
        trimmed["nameres_version"] = sanitize(raw["nameres_version"], 50)
    queries = raw.get("recent_queries")
    if isinstance(queries, dict):
        latencies = {
            out_key: _trimmed_float(queries.get(in_key))
            for out_key, in_key in [
                ("mean_ms", "mean_time_ms"),
                ("p50_ms", "p50_ms"),
                ("p95_ms", "p95_ms"),
                ("p99_ms", "p99_ms"),
            ]
        }
        trimmed["recent_queries"] = {
            key: value for key, value in latencies.items() if value is not None
        }
    # NameRes's search index: under "solr" before v1.7, at the top level from
    # v1.7 on, and at the top level in NameRes ES (which reports numDocs and
    # size, both 0 on ci-nameres-es). One "index" key whichever it was. Keyed
    # on the service as well as the shape, as "version" is above: a NodeNorm
    # body carrying a numDocs is not a NameRes index.
    solr = raw.get("solr")
    index = solr if isinstance(solr, dict) else raw
    if service == "nameres" and (isinstance(solr, dict) or "numDocs" in raw):
        trimmed_index = {}
        num_docs = _trimmed_int(index.get("numDocs"))
        if num_docs is not None:
            trimmed_index["numDocs"] = num_docs
        if "size" in index:
            trimmed_index["size"] = sanitize(index["size"], 20)
        for key in ("lastModified", "startTime"):
            if key in index:
                trimmed_index[key] = sanitize(index[key], 40)
        trimmed["index"] = trimmed_index
    return trimmed


def service_links(base_url, backend):
    """
    The docs and /status URLs of a service, from its targets.ini base URL and
    backend. The Redis- and Solr-backed services serve Swagger UI at /docs; the
    Elasticsearch-backed ones serve it at their root and answer /docs with a
    404 (checked on nodenorm-es and namelookup-es on 2026-11-11). Both URLs come
    from checked-in config, so the website may link to them.
    """
    if not base_url:
        return None, None
    docs = base_url if backend == "elasticsearch" else base_url.rstrip("/") + "/docs"
    return docs, base_url.rstrip("/") + "/status"


def fetch_status(status_url, service):
    """GET a service's /status URL (from service_links) and whitelist it, adding
    how long it took to answer. Errors become just a type name — no message
    text, since it could echo the URL or response body."""
    if not status_url:
        # A targets.ini section that defines only one of the two services: one
        # blank card, not a crashed report.
        return {"error": "NoURL"}
    try:
        # Timed by hand rather than with response.elapsed, which stops when the
        # headers arrive and so leaves out downloading and parsing the body.
        start = time.monotonic()
        response = requests.get(status_url, timeout=STATUS_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()
        elapsed_ms = round((time.monotonic() - start) * 1000)
        status = trim_status(body, service)
        # A body that is not a JSON object is reported as InvalidStatus, with
        # no timing: how fast a service answered with garbage says nothing.
        if isinstance(body, dict):
            status["response_ms"] = elapsed_ms
        return status
    except Exception as e:
        logger.warning(
            "Could not fetch status from %r: %s", status_url, type(e).__name__
        )
        return {"error": type(e).__name__}


def read_raw_records(raw_dir):
    """Read every *.jsonl file in raw_dir. Bad lines are logged and skipped —
    one corrupt line must not sink the whole report."""
    records = []
    for path in sorted(Path(raw_dir).glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict) or not isinstance(
                        record.get("id"), str
                    ):
                        raise ValueError("not a record object")
                    records.append(record)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Skipping bad line %s:%d: %s", path, line_number, e)
    return records


def build_results(records, targets, allowlist):
    """
    Aggregate raw records into the report's results dict, plus per-target
    outcome counts and whether the GitHub issue tests produced any results.
    """
    # (key, target) -> list of records, plus key -> records across all targets
    by_test = {}
    by_key = {}
    for record in records:
        key, target, rest = parse_nodeid(record["id"], targets)
        by_test.setdefault((key, target, rest), []).append(record)
        by_key.setdefault(key, []).append(record)

    results = {}
    counts = {
        target: {outcome: 0 for outcome in OUTCOME_SEVERITY}
        for target in list(targets) + ["?"]
    }
    github_issues_ran = False

    for (key, target, rest), test_records in by_test.items():
        outcome = max(
            (classify_record(r) for r in test_records),
            key=lambda o: OUTCOME_SEVERITY[o],
        )
        counts[target][outcome] += 1

        # Only the real issue-driven tests count — github_issues/unit/ are
        # unit tests of the parser and run without a token.
        if key.startswith("github_issues/test_github_issues.py"):
            github_issues_ran = True

        if target == "?":
            # No target could be parsed out of the node ID. Results.vue renders
            # one column per entry of report["targets"], which never includes
            # "?", so such a row would show a label above an entirely blank set
            # of cells with nothing on the page to explain it. These are
            # reported through unattributed_counts instead.
            continue

        result = results.setdefault(key, {"outcomes": {}})
        cell = {"o": outcome}
        # Blocklist messages are withheld unconditionally, before any cell is
        # built — the blocklist sheet may not be public, and the messages
        # interpolate its entries.
        if outcome in OUTCOMES_WITH_MESSAGES and "test_blocklist.py" not in key:
            # str() for the same reason as in classify_record: join() raises
            # on a non-string, and that would sink every other result too.
            messages = [str(r["msg"]) for r in test_records if r.get("msg")]
            if messages:
                cell["msg"] = sanitize("\n---\n".join(messages))
        result["outcomes"][target] = cell

        if "kind" not in result:
            _annotate_result(result, key, rest, by_key[key], allowlist)

    return results, counts, github_issues_ran


def _annotate_result(result, key, rest, test_records, allowlist):
    """Attach kind and validated metadata/link parts to one result."""
    if "test_blocklist.py" in key:
        # The blocklist sheet may not be public: no metadata, no links.
        # Messages are already withheld in build_results.
        result["kind"] = "blocklist"
        return

    if key.startswith("github_issues/"):
        issue = validate_issue_id(rest, allowlist)
        if issue:
            result["kind"] = "issue"
            result["issue"] = issue
            return
        result["kind"] = "other"
        return

    row_match = re.search(r":row=([0-9]+)$", rest)
    if "_from_gsheet.py" in key and row_match:
        result["kind"] = "gsheet"
        result["row"] = int(row_match.group(1))
        props = {}
        for record in test_records:
            props.update(record.get("props") or {})
        for prop in ("category", "source", "query_id", "query_label"):
            if props.get(prop):
                result[prop] = sanitize(props[prop], 200)
        source_url = validate_source_url(props.get("source_url"), allowlist)
        if source_url:
            result["source_url"] = source_url
        return

    result["kind"] = "other"


def build_report(results, counts, github_issues_ran, targets, allowlist, config):
    now = datetime.datetime.now(datetime.timezone.utc)
    target_sections = {}
    for target in targets:
        section = config[target]
        nodenorm_url = section.get("NodeNormURL")
        nameres_url = section.get("NameResURL")
        # The configured backend rather than the one /status reports: NameRes
        # /status does not report one, and the NodeNorm tests already check the
        # configured one against /status. None for a service the environment
        # does not run, or the Backend row would name one beside "NoURL".
        nodenorm_backend = (
            section.get("NodeNormBackend", "redis") if nodenorm_url else None
        )
        nameres_backend = section.get("NameResBackend", "solr") if nameres_url else None
        nodenorm_docs_url, nodenorm_status_url = service_links(
            nodenorm_url, nodenorm_backend
        )
        nameres_docs_url, nameres_status_url = service_links(
            nameres_url, nameres_backend
        )
        target_counts = counts[target]
        total = sum(target_counts.values())
        target_sections[target] = {
            "nodenorm_url": nodenorm_url,
            "nameres_url": nameres_url,
            "nodenorm_backend": nodenorm_backend,
            "nameres_backend": nameres_backend,
            "nodenorm_docs_url": nodenorm_docs_url,
            "nodenorm_status_url": nodenorm_status_url,
            "nameres_docs_url": nameres_docs_url,
            "nameres_status_url": nameres_status_url,
            "nodenorm_status": fetch_status(nodenorm_status_url, "nodenorm"),
            "nameres_status": fetch_status(nameres_status_url, "nameres"),
            "counts": target_counts,
            "unreachable": total == 0 or target_counts["error"] == total,
        }
    report = {
        "generated_at": now.isoformat(timespec="seconds"),
        "run": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "git_sha": os.environ.get("GITHUB_SHA"),
        },
        "repos_allowlist": allowlist,
        "github_issues_ran": github_issues_ran,
        "targets": target_sections,
        "results": results,
    }
    # Tests without a recognizable target only appear if something ran them.
    if any(counts["?"].values()):
        report["unattributed_counts"] = counts["?"]
    return report


def build_history_line(report):
    """The compact per-run summary appended to history.jsonl."""
    line = {
        "date": report["generated_at"][:10],
        "run_id": report["run"]["github_run_id"],
        "targets": {},
    }
    for target, section in report["targets"].items():
        nodenorm_status = section["nodenorm_status"]
        nameres_status = section["nameres_status"]
        eq_db = nodenorm_status.get("databases", {}).get("eq_id_to_id_db", {})
        index = nameres_status.get("index", {})
        line["targets"][target] = {
            "babel_version": nodenorm_status.get("babel_version"),
            "nameres_version": nameres_status.get("nameres_version"),
            # NodeNorm and NameRes are promoted separately, so each release
            # change shows up in the history diff on its own.
            "nameres_babel_version": nameres_status.get("babel_version"),
            "biolink_version": nodenorm_status.get("biolink_version"),
            "nn_eq_records": eq_db.get("count"),
            # Named for Solr, but read from either backend's index. Runs before
            # 2026-11 read only the pre-v1.7 "solr" key, so they recorded null
            # for NameRes v1.7+ environments: a null followed by a number in
            # these two fields is data that was missing, not a change. Anything
            # that compares them across runs must skip a null, as History.vue
            # skips fields an older run did not record.
            "solr_docs": index.get("numDocs"),
            "solr_size": index.get("size"),
            "p95_ms": nameres_status.get("recent_queries", {}).get("p95_ms"),
            "counts": section["counts"],
        }
    return line


def all_targets_unreachable(report):
    return all(section["unreachable"] for section in report["targets"].values())


def run_has_tests(run):
    """True if any target in a history run recorded at least one test. A run
    where none did is a broken run, not a data point — the workflow died before
    pytest reported anything — and history carries every line forward forever,
    so such a row would sit in the trends table indefinitely."""
    for target in run.get("targets", {}).values():
        counts = target.get("counts") if isinstance(target, dict) else None
        if isinstance(counts, dict) and any(
            isinstance(n, int) and n > 0 for n in counts.values()
        ):
            return True
    return False


def append_history(history_in_path, history_line):
    """Return the new history.jsonl content: prior lines verbatim (bad and
    empty ones dropped so the file can never poison future runs), new line
    appended unless this run recorded nothing either."""
    lines = []
    if history_in_path and os.path.isfile(history_in_path):
        with open(history_in_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    prior = json.loads(line)
                    if not isinstance(prior, dict) or not isinstance(
                        prior.get("targets"), dict
                    ):
                        raise ValueError("not a history object")
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Dropping bad history line: %.80r", line)
                    continue
                if not run_has_tests(prior):
                    logger.warning(
                        "Dropping history run with no test results: %.80r", line
                    )
                    continue
                lines.append(line)
    if run_has_tests(history_line):
        lines.append(json.dumps(history_line))
    else:
        logger.warning("This run recorded no test results: not adding it to history")
    return "\n".join(lines) + "\n" if lines else ""


def main(argv=None):
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        required=True,
        help="Directory of *.jsonl files from pytest --report-jsonl",
    )
    parser.add_argument(
        "--targets-ini", required=True, help="Path to tests/targets.ini"
    )
    parser.add_argument(
        "--history-in",
        default=None,
        help="Previous history.jsonl to append to (may be missing)",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory to write report.json and history.jsonl into",
    )
    args = parser.parse_args(argv)

    targets, allowlist, config = read_targets(args.targets_ini)
    records = read_raw_records(args.raw_dir)
    logger.info("Read %d raw records for targets %s", len(records), targets)
    results, counts, github_issues_ran = build_results(records, targets, allowlist)
    report = build_report(
        results, counts, github_issues_ran, targets, allowlist, config
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        # allow_nan=False so this fails loudly rather than writing a file no
        # browser can parse, if a non-finite ever reaches here by another route.
        json.dump(report, f, separators=(",", ":"), allow_nan=False)
    with open(out_dir / "history.jsonl", "w", encoding="utf-8") as f:
        f.write(append_history(args.history_in, build_history_line(report)))
    logger.info(
        "Wrote %s (%d results) and %s",
        out_dir / "report.json",
        len(results),
        out_dir / "history.jsonl",
    )
    # Zero results everywhere means the test runs themselves broke (e.g. every
    # xdist worker crashed at startup), not that six environments all went
    # down at once. Fail loudly so the workflow stops before deploying an
    # empty dashboard; the files are still written for debugging.
    if all_targets_unreachable(report):
        logger.error("Every target is unreachable — refusing to succeed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
