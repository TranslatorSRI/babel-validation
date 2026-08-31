"""Unit tests for the dashboard report generator. No network: everything is fed
literal JSONL records and hostile inline payloads."""

import configparser
import json

import pytest

from src.babel_validation.tools import generate_report
from src.babel_validation.tools.generate_report import (
    append_history,
    build_results,
    classify_record,
    fetch_status,
    parse_nodeid,
    read_raw_records,
    read_targets,
    sanitize,
    split_target,
    trim_status,
    validate_issue_id,
    validate_source_url,
)

pytestmark = pytest.mark.unit

TARGETS = ["prod", "test", "ci", "ci-es", "dev", "exp"]
ALLOWLIST = ["ncatstranslator/babel", "translatorsri/babel-validation"]


def _record(
    nodeid, outcome="passed", when="call", wasxfail=False, msg=None, props=None
):
    return {
        "id": nodeid,
        "when": when,
        "outcome": outcome,
        "wasxfail": wasxfail,
        "duration": 0.1,
        "props": props or {},
        "msg": msg,
    }


class TestTargetExtraction:
    def test_hyphenated_target_matches_longest_first(self):
        assert split_target("ci-es-foo:row=1", TARGETS) == ("ci-es", "foo:row=1")
        assert split_target("ci-foo", TARGETS) == ("ci", "foo")

    def test_target_as_suffix(self):
        # Current pytest puts the module-level parametrize first, target last.
        assert split_target("test_label:row=251-prod", TARGETS) == (
            "prod",
            "test_label:row=251",
        )
        assert split_target("test_label:row=251-ci-es", TARGETS) == (
            "ci-es",
            "test_label:row=251",
        )

    def test_unknown_target(self):
        assert split_target("staging-foo", TARGETS) == (None, "staging-foo")

    def test_parse_nodeid_strips_target_from_key(self):
        key, target, rest = parse_nodeid(
            "nodenorm/test_nodenorm_from_gsheet.py::test_normalization"
            "[dev-test_nodenorm_from_gsheet.test_row:row=131]",
            TARGETS,
        )
        assert target == "dev"
        assert rest == "test_nodenorm_from_gsheet.test_row:row=131"
        assert key == (
            "nodenorm/test_nodenorm_from_gsheet.py::test_normalization"
            "[test_nodenorm_from_gsheet.test_row:row=131]"
        )

    def test_parse_nodeid_strips_the_rootdir_relative_tests_prefix(self):
        # `pytest tests --target dev` produces tests/-prefixed node IDs;
        # `pytest tests/nodenorm/...` does not. Keys must be identical.
        prefixed, _, _ = parse_nodeid(
            "tests/nodenorm/test_nodenorm_from_gsheet.py::test_normalization[x:row=1-dev]",
            TARGETS,
        )
        bare, _, _ = parse_nodeid(
            "nodenorm/test_nodenorm_from_gsheet.py::test_normalization[x:row=1-dev]",
            TARGETS,
        )
        assert prefixed == bare
        assert prefixed.startswith("nodenorm/")

    def test_parse_nodeid_without_params_goes_to_unknown_bucket(self):
        key, target, rest = parse_nodeid("tests/test_cache_dir.py::test_mode", TARGETS)
        assert (key, target) == ("test_cache_dir.py::test_mode", "?")

    def test_parse_nodeid_unknown_target_does_not_crash(self):
        key, target, rest = parse_nodeid("x.py::t[staging-row=1]", TARGETS)
        assert target == "?"
        assert key == "x.py::t[staging-row=1]"


class TestClassification:
    @pytest.mark.parametrize(
        "outcome,when,wasxfail,msg,expected",
        [
            ("passed", "call", False, None, "passed"),
            ("failed", "call", False, "AssertionError: nope", "failed"),
            ("skipped", "call", True, "reason", "xfailed"),
            ("passed", "call", True, None, "xpassed"),  # imperative pytest.xfail
            ("failed", "call", False, "[XPASS(strict)] issue is open", "xpassed"),
            ("skipped", "setup", False, "category filter", "skipped"),
            ("failed", "setup", False, "fixture blew up", "error"),
            ("failed", "teardown", False, "cleanup blew up", "error"),
        ],
    )
    def test_single_record(self, outcome, when, wasxfail, msg, expected):
        record = _record("x.py::t[dev-p]", outcome, when, wasxfail, msg)
        assert classify_record(record) == expected

    def test_subtest_aggregation_worst_wins_and_messages_join(self):
        nodeid = "github_issues/test_github_issues.py::test_github_issue[dev-NCATSTranslator/Babel#12]"
        records = [
            _record(nodeid, "passed"),
            _record(nodeid, "failed", msg="subtest one failed"),
            _record(nodeid, "passed"),
        ]
        results, counts, ran = build_results(records, TARGETS, ALLOWLIST)
        key = "github_issues/test_github_issues.py::test_github_issue[NCATSTranslator/Babel#12]"
        assert results[key]["outcomes"]["dev"]["o"] == "failed"
        assert "subtest one failed" in results[key]["outcomes"]["dev"]["msg"]
        assert counts["dev"]["failed"] == 1
        assert sum(counts["dev"].values()) == 1  # aggregated, not three tests
        assert ran is True


class TestLinkValidation:
    def test_issue_id_allowlisted(self):
        assert (
            validate_issue_id("NCATSTranslator/Babel#12", ALLOWLIST)
            == "NCATSTranslator/Babel#12"
        )

    @pytest.mark.parametrize(
        "issue_id",
        [
            "evil/repo#1",
            "NCATSTranslator/Babel#notanumber",
            "NCATSTranslator/Babel/extra#1",
            "../etc#1",
            "",
            None,
        ],
    )
    def test_issue_id_rejected(self, issue_id):
        assert validate_issue_id(issue_id, ALLOWLIST) is None

    def test_source_url_allowlisted(self):
        url = "https://github.com/NCATSTranslator/Babel/issues/12"
        assert validate_source_url(url, ALLOWLIST) == url

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com.evil.example/NCATSTranslator/Babel/issues/12",
            "https://github.com/evil/repo/issues/1",
            "https://github.com/NCATSTranslator",
            "http://github.com/NCATSTranslator/Babel/issues/12",
            "javascript:alert(1)",
            "",
            None,
        ],
    )
    def test_source_url_rejected(self, url):
        assert validate_source_url(url, ALLOWLIST) is None


class TestResultAnnotation:
    def test_gsheet_row_and_props(self):
        nodeid = (
            "nodenorm/test_nodenorm_from_gsheet.py::test_normalization"
            "[dev-test_nodenorm_from_gsheet.test_row:row=131]"
        )
        records = [
            _record(
                nodeid,
                "failed",
                msg="AssertionError: wrong id",
                props={
                    "category": "Diseases",
                    "source": "hetio",
                    "source_url": "https://github.com/NCATSTranslator/Babel/issues/12",
                    "query_id": "MONDO:0005148",
                    "query_label": "type 2 diabetes",
                },
            )
        ]
        results, _, _ = build_results(records, TARGETS, ALLOWLIST)
        (result,) = results.values()
        assert result["kind"] == "gsheet"
        assert result["row"] == 131
        assert result["category"] == "Diseases"
        assert result["query_id"] == "MONDO:0005148"
        assert (
            result["source_url"] == "https://github.com/NCATSTranslator/Babel/issues/12"
        )

    def test_gsheet_props_merged_across_targets(self):
        # dev errors during setup, before record_property runs, so its records
        # carry no props. The row must still get its metadata from prod.
        base = "nodenorm/test_nodenorm_from_gsheet.py::test_normalization[%s-r:row=7]"
        records = [
            _record(base % "dev", "error", when="setup", msg="boom"),
            _record(base % "prod", "passed", props={"category": "Genes"}),
        ]
        results, _, _ = build_results(records, TARGETS, ALLOWLIST)
        (result,) = results.values()
        assert result["category"] == "Genes"

    def test_gsheet_bad_source_url_omitted(self):
        nodeid = "nameres/test_nameres_from_gsheet.py::test_label[prod-x:row=5]"
        records = [
            _record(
                nodeid, "failed", msg="m", props={"source_url": "https://evil.example/"}
            )
        ]
        results, _, _ = build_results(records, TARGETS, ALLOWLIST)
        (result,) = results.values()
        assert "source_url" not in result

    def test_issue_not_in_allowlist_becomes_other_without_link(self):
        nodeid = (
            "github_issues/test_github_issues.py::test_github_issue[dev-evil/repo#1]"
        )
        results, _, ran = build_results([_record(nodeid, "passed")], TARGETS, ALLOWLIST)
        (result,) = results.values()
        assert result["kind"] == "other"
        assert "issue" not in result
        assert ran is True  # the suite ran even if the id was rejected

    def test_no_issue_records_means_not_ran(self):
        records = [_record("nodenorm/test_x.py::t[dev-p]", "passed")]
        _, _, ran = build_results(records, TARGETS, ALLOWLIST)
        assert ran is False

    def test_issue_records_with_tests_prefix_count_as_ran(self):
        # The exact shape the daily workflow produces (`pytest tests ...`).
        nodeid = "tests/github_issues/test_github_issues.py::test_github_issue[NCATSTranslator/Babel#71-ci]"
        results, _, ran = build_results([_record(nodeid, "passed")], TARGETS, ALLOWLIST)
        assert ran is True
        (result,) = results.values()
        assert result["kind"] == "issue"
        assert result["issue"] == "NCATSTranslator/Babel#71"

    def test_issue_unit_tests_do_not_count_as_ran(self):
        # github_issues/unit/ are unit tests of the parser: they run without a
        # token, so they must not make the report claim the issue tests ran.
        nodeid = "tests/github_issues/unit/test_syntax.py::TestX::test_y[some-param]"
        _, _, ran = build_results([_record(nodeid, "passed")], TARGETS, ALLOWLIST)
        assert ran is False

    def test_blocklist_redacted_for_every_target(self):
        base = "nameres/test_blocklist.py::test_blocklist_entry"
        records = [
            _record(f"{base}[dev-blocklist_entry0]", "failed", msg="secret entry text"),
            _record(
                f"{base}[prod-blocklist_entry0]", "failed", msg="secret entry text"
            ),
        ]
        results, _, _ = build_results(records, TARGETS, ALLOWLIST)
        (result,) = results.values()
        assert result["kind"] == "blocklist"
        assert "secret" not in json.dumps(results)
        for cell in result["outcomes"].values():
            assert "msg" not in cell


class TestNoSheetLeak:
    def test_report_never_contains_the_sheet_id_or_a_sheet_link(self, monkeypatch):
        # The public report must not let casual observers find the Google Sheet.
        # The generator must not read the sheet ID at all, so plant a fake one in
        # the environment and check it cannot surface in the output.
        sheet_id = "FAKE-SHEET-ID-FOR-LEAK-TEST-0123456789"
        monkeypatch.setenv("BABEL_VALIDATION_SHEET_ID", sheet_id)
        monkeypatch.setattr(
            generate_report, "fetch_status", lambda url: {"status": "ok"}
        )
        records = [
            _record(
                "nodenorm/test_nodenorm_from_gsheet.py::test_normalization[dev-x:row=42]",
                "failed",
                msg="boom",
                props={"category": "Diseases", "query_id": "MONDO:1"},
            )
        ]
        results, counts, ran = build_results(records, TARGETS, ALLOWLIST)
        config = configparser.ConfigParser()
        config.read_string(
            "[dev]\nNodeNormURL = https://nn.example/\nNameResURL = https://nr.example/\n"
        )
        report = generate_report.build_report(
            results, counts, ran, ["dev"], ALLOWLIST, config
        )
        dumped = json.dumps(report)
        assert sheet_id not in dumped
        assert "docs.google.com" not in dumped


class TestSanitize:
    def test_truncates(self):
        assert sanitize("a" * 1000).startswith("a" * 500)
        assert sanitize("a" * 1000).endswith("[truncated]")

    def test_escapes_ansi_and_controls(self):
        hostile = "red \x1b[31malert\x07 ‮done"
        cleaned = sanitize(hostile)
        assert "\x1b" not in cleaned and "\x07" not in cleaned and "‮" not in cleaned
        assert "\\x1b" in cleaned  # escaped, visibly, not silently stripped

    def test_keeps_newlines_and_tabs(self):
        assert sanitize("a\nb\tc") == "a\nb\tc"

    def test_none(self):
        assert sanitize(None) is None


class TestTrimStatus:
    def test_hostile_payload(self):
        hostile = {
            "status": "ok\x1b[2Jcleared",
            "babel_version": "x" * 5000,
            "babel_version_url": "https://evil.example/NCATSTranslator/",
            "biolink_model": {"tag": "v4", "download_url": "https://evil.example/"},
            "databases": {
                "eq_id_to_id_db": {
                    "count": "12345",
                    "used_memory_rss_human": "9G" * 50,
                },
                "weird": "not a dict",
            },
            "recent_queries": {"mean_time_ms": "NaNish", "p95_ms": "12.5"},
            "solr": {"numDocs": 7, "size": "1 GB", "jvm": {"secrets": True}},
            "extra_key": {"anything": "dropped"},
        }
        trimmed = trim_status(hostile)
        assert "extra_key" not in trimmed
        assert "babel_version_url" not in trimmed  # not the NCATSTranslator org
        assert "\x1b" not in trimmed["status"]
        assert len(trimmed["babel_version"]) < 100
        assert trimmed["databases"]["eq_id_to_id_db"]["count"] == 12345
        assert (
            len(trimmed["databases"]["eq_id_to_id_db"]["used_memory_rss_human"]) <= 32
        )
        assert "weird" not in trimmed["databases"]
        assert trimmed["recent_queries"] == {"p95_ms": 12.5}
        assert trimmed["solr"] == {"numDocs": 7, "size": "1 GB"}
        assert trimmed["biolink_version"] == "v4"

    def test_valid_babel_version_url_kept(self):
        trimmed = trim_status(
            {"babel_version_url": "https://github.com/ncatstranslator/Babel/blob/x.md"}
        )
        assert trimmed["babel_version_url"].startswith("https://github.com/")

    def test_not_a_dict(self):
        assert trim_status(["nope"]) == {"error": "InvalidStatus"}


class TestAllTargetsUnreachable:
    def test_all_unreachable_means_the_run_broke(self):
        report = {
            "targets": {"dev": {"unreachable": True}, "prod": {"unreachable": True}}
        }
        assert generate_report.all_targets_unreachable(report) is True

    def test_one_reachable_target_is_enough(self):
        report = {
            "targets": {"dev": {"unreachable": True}, "prod": {"unreachable": False}}
        }
        assert generate_report.all_targets_unreachable(report) is False


def _run(date, passed=1):
    return {"date": date, "targets": {"dev": {"counts": {"passed": passed}}}}


class TestHistory:
    def test_append_keeps_old_lines_verbatim(self, tmp_path):
        old = tmp_path / "history.jsonl"
        line1 = json.dumps(_run("2026-08-24"))
        line2 = json.dumps(_run("2026-08-25"))
        old.write_text(f"{line1}\n{line2}\nnot json\n", encoding="utf-8")
        new_line = _run("2026-08-26")
        content = append_history(str(old), new_line)
        lines = content.strip().split("\n")
        assert lines[0] == line1
        assert lines[1] == line2
        assert json.loads(lines[2]) == new_line
        assert len(lines) == 3  # the bad line is dropped

    def test_missing_history_file(self):
        run = _run("2026-08-26")
        assert append_history("/nonexistent/history.jsonl", run) == (
            json.dumps(run) + "\n"
        )

    def test_run_without_any_test_results_is_dropped(self, tmp_path):
        # The shakedown run that died before pytest reported anything: real
        # /status values, every count zero. History carries lines forward
        # forever, so it has to be dropped rather than merely not written.
        empty = {
            "date": "2026-08-27",
            "targets": {"dev": {"babel_version": "2025sep1", "counts": {"passed": 0}}},
        }
        old = tmp_path / "history.jsonl"
        old.write_text(json.dumps(empty) + "\n", encoding="utf-8")
        real = _run("2026-08-28")
        assert append_history(str(old), real) == json.dumps(real) + "\n"
        assert append_history(str(old), empty) == ""


class TestBadInputIsSkippedNotFatal:
    def test_non_string_id_is_skipped(self, tmp_path, caplog):
        (tmp_path / "raw.jsonl").write_text(
            json.dumps({"id": 5})
            + "\n"
            + json.dumps(_record("a/b.py::t[dev-x]"))
            + "\n",
            encoding="utf-8",
        )
        records = read_raw_records(str(tmp_path))
        assert [r["id"] for r in records] == ["a/b.py::t[dev-x]"]

    def test_history_line_without_targets_is_dropped(self, tmp_path):
        old = tmp_path / "history.jsonl"
        good = json.dumps(_run("2026-08-24"))
        old.write_text(f"{good}\nnull\n123\n{{}}\n", encoding="utf-8")
        lines = append_history(str(old), _run("2026-08-26")).strip().split("\n")
        assert lines[0] == good
        assert len(lines) == 2

    def test_missing_url_does_not_reach_the_network(self):
        assert fetch_status(None) == {"error": "NoURL"}


# read_targets is the single source of truth for which environments exist: as of
# the dashboard workflow taking its loop from it, a section it returns is one that
# gets run, and one it drops is never mentioned again. When those two disagreed,
# the extra target reached the site as a permanently unreachable column.
class TestReadTargets:
    def _ini(self, tmp_path, text):
        path = tmp_path / "targets.ini"
        path.write_text(text, encoding="utf8")
        return path

    def test_it_returns_every_section_except_localhost(self, tmp_path):
        path = self._ini(
            tmp_path,
            "[DEFAULT]\nRepositories =\n    org/one\n\n"
            "[prod]\nNodeNormURL = https://prod.example/\n\n"
            "[test-redis]\nNodeNormURL = https://redis.example/\n\n"
            "[localhost]\nNodeNormURL = http://localhost:2434/\n",
        )

        targets, allowlist, _ = read_targets(path)

        assert targets == ["prod", "test-redis"]
        assert allowlist == ["org/one"]

    def test_it_keeps_the_order_the_file_gives(self, tmp_path):
        # The site sorts by DEPLOYMENT_ORDER, but the workflow runs them in this
        # order, and a report is easier to read against the file it came from.
        path = self._ini(tmp_path, "".join(f"[{name}]\nNodeNormURL = https://{name}.example/\n\n"
                                           for name in ("exp", "dev", "ci", "prod")))

        assert read_targets(path)[0] == ["exp", "dev", "ci", "prod"]

    def test_the_repository_allowlist_is_lowercased_and_stripped(self, tmp_path):
        path = self._ini(
            tmp_path,
            "[DEFAULT]\nRepositories =\n    NCATSTranslator/Babel\n   \n    TranslatorSRI/Babel-Explorer\n\n"
            "[prod]\nNodeNormURL = https://prod.example/\n",
        )

        assert read_targets(path)[1] == ["ncatstranslator/babel", "translatorsri/babel-explorer"]

    def test_the_checked_in_targets_ini_has_no_localhost_and_is_not_empty(self):
        targets, _, _ = read_targets("tests/targets.ini")

        assert "localhost" not in targets
        assert targets, "the workflow builds its run loop from this list"
