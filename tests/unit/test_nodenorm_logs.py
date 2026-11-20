"""The NodeNorm log reader must parse what NodeNorm logs and say what it left out.

No log exports are checked in, so these build small ones: a Loki export is a JSON list of
[query, response] pairs, and the Sterling archives hold each as a .json with a .csv twin.
"""

import io
import json
import tarfile

import pytest

from src.babel_validation.tools.nodenorm_logs import (
    count_curies,
    curies_in,
    load_logs,
    merge_windows,
    parse_log_line,
)

pytestmark = pytest.mark.unit

OPTIONS = (
    "conflate_gene_protein=True, conflate_chemical_drug=False, "
    "include_descriptions=False, include_individual_types=True"
)


def log_line(curies, ms="1.21", time="2026-01-29 23:00:18,433"):
    return (
        f"{time} | INFO | normalizer:get_normalized_nodes | "
        f"Normalized {len(curies)} nodes in {ms} ms with arguments (curies={curies!r}, {OPTIONS})"
    )


def loki_export(lines, pod="pod-a", start=0, end=3_600_000_000_000, first_timestamp=0):
    stream = {"pod": pod, "node_name": "k8s-node01", "namespace": "translator-dev"}
    values = [[str(first_timestamp + i), line] for i, line in enumerate(lines)]
    return [
        [
            {"start": start, "end": end},
            {"data": {"result": [{"stream": stream, "values": values}]}},
        ]
    ]


def add_member(tar, name, text):
    data = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def test_parses_a_request_line():
    request = parse_log_line(log_line(["UMLS:C0132098", "MONDO:0005148"], ms="8.79"))
    assert request.time == "2026-01-29 23:00:18.433"
    assert request.curie_count == 2
    assert request.time_taken_ms == 8.79
    assert request.options == OPTIONS
    assert request.first_prefix == "UMLS"
    assert curies_in(request.curies_text) == ["UMLS:C0132098", "MONDO:0005148"]


def test_parses_a_line_prefixed_with_the_shippers_timestamp():
    request = parse_log_line("2025-06-18T03:26:30-04:00\t" + log_line(["GO:0006954"]))
    assert (request.curie_count, request.first_prefix) == (1, "GO")


def test_a_truncated_line_keeps_its_count_and_time_but_not_its_options():
    line = log_line([f"CHEBI:{i}" for i in range(500)], ms="603.5")
    request = parse_log_line(line[:2000])
    assert (request.curie_count, request.time_taken_ms) == (500, 603.5)
    assert request.options is None


def test_a_curie_that_looks_like_the_end_of_the_list_does_not_end_it():
    request = parse_log_line(log_line(["A:1], x=True)", "B:2"]))
    assert request.options == OPTIONS
    assert curies_in(request.curies_text) == ["A:1], x=True)", "B:2"]


@pytest.mark.parametrize(
    "line",
    [
        '[2025-06-23 10:21:30 +0000] [21] [INFO] 10.11.72.202:51412 - "GET /docs HTTP/1.1" 200',
        "",
        "2026-01-29 23:00:18,433 | INFO | normalizer:get_normalized_nodes | something else",
    ],
)
def test_other_lines_are_not_requests(line):
    assert parse_log_line(line) is None


def test_loads_an_archive_and_reports_what_it_skipped(tmp_path):
    first = log_line(["UMLS:C1"], ms="2.5", time="2026-01-01 00:00:01,000")
    slow = log_line(["CHEBI:1", "CHEBI:2"], ms="1500.0", time="2026-01-01 00:00:02,000")
    with tarfile.open(tmp_path / "logs-2026-01.tar.gz", "w:gz") as tar:
        add_member(
            tar,
            "2026-01/a.json",
            json.dumps(loki_export([first, slow, "not a request"])),
        )
        add_member(tar, "2026-01/a.csv", "pod,log_entry\n")
        # The next page of the same query repeats the last row of the page before it.
        add_member(
            tar, "2026-01/b.json", json.dumps(loki_export([slow], first_timestamp=1))
        )
        add_member(tar, "2026-01/run.txt", "Fetched 2 log entries\n")
    (tmp_path / "cloudwatch.json").write_text(json.dumps([{"@message": first}]))
    (tmp_path / ".DS_Store").write_text("ignored")

    loaded = load_logs(tmp_path)

    assert loaded.columns["time_taken_ms"] == [2.5, 1500.0]
    assert loaded.columns["curie_count"] == [1, 2]
    assert loaded.columns["pod"] == ["pod-a", "pod-a"]
    assert loaded.columns["node_name"] == ["k8s-node01"] * 2
    assert loaded.columns["first_prefix"] == ["UMLS", "CHEBI"]
    # Only slow requests keep a preview of what was asked for.
    assert loaded.columns["curies_preview"] == ["", "'CHEBI:1', 'CHEBI:2'"]

    cloudwatch, archive = loaded.files
    assert (cloudwatch.path, cloudwatch.status) == ("cloudwatch.json", "skipped")
    assert "not a Loki export" in cloudwatch.notes
    assert (archive.status, archive.format) == ("loaded", "tar archive")
    assert (archive.members_read, archive.requests, archive.curies) == (2, 2, 3)
    assert (archive.duplicates, archive.other_lines) == (1, 1)
    assert (archive.first_request, archive.last_request) == (
        "2026-01-01 00:00:01.000",
        "2026-01-01 00:00:02.000",
    )
    assert archive.windows == [(0, 3_600_000_000_000)] * 2
    assert archive.hours_queried == 1.0
    assert archive.skipped == {
        "CSV twin of a JSON export": 1,
        "no reader for '.txt' files": 1,
    }


def test_merges_overlapping_and_touching_windows():
    assert merge_windows([(5, 9), (0, 2), (2, 3), (6, 7), (20, 30)]) == [
        (0, 3),
        (5, 9),
        (20, 30),
    ]
    assert merge_windows([]) == []


def test_the_same_line_from_two_pods_is_two_requests(tmp_path):
    line = log_line(["UMLS:C1"])
    (tmp_path / "a.json").write_text(json.dumps(loki_export([line], pod="pod-a")))
    (tmp_path / "b.json").write_text(json.dumps(loki_export([line], pod="pod-b")))
    assert load_logs(tmp_path).columns["pod"] == ["pod-a", "pod-b"]


def test_the_same_line_logged_twice_by_one_pod_is_two_requests(tmp_path):
    # Seen in the dev logs: identical text, down to the millisecond and the timing, but two
    # Loki entries. Only a repeat of the same entry is a duplicate.
    line = log_line(["UMLS:C1"])
    (tmp_path / "a.json").write_text(json.dumps(loki_export([line, line])))
    (tmp_path / "copy-of-a.json").write_text(json.dumps(loki_export([line, line])))
    loaded = load_logs(tmp_path)
    assert loaded.columns["curie_count"] == [1, 1]
    assert [f.duplicates for f in loaded.files] == [0, 2]


def test_a_broken_file_is_reported_and_the_rest_still_load(tmp_path):
    (tmp_path / "a-broken.tar.gz").write_bytes(b"this is not a tar archive")
    (tmp_path / "b.json").write_text(json.dumps(loki_export([log_line(["UMLS:C1"])])))
    # Right outer shape, wrong inside: the response has no "data".
    (tmp_path / "c.json").write_text(json.dumps([[{"start": 0, "end": 1}, {}]]))

    loaded = load_logs(tmp_path)

    assert [f.status for f in loaded.files] == ["error", "loaded", "error"]
    assert loaded.columns["curie_count"] == [1]


def test_counts_each_curie_once_per_distinct_request(tmp_path):
    lines = [log_line(["UMLS:C1", "GO:1"]), log_line(["UMLS:C1"], ms="3.0")]
    (tmp_path / "a.json").write_text(json.dumps(loki_export(lines)))
    (tmp_path / "copy-of-a.json").write_text(json.dumps(loki_export(lines)))
    assert count_curies(tmp_path) == {"UMLS:C1": 2, "GO:1": 1}
