"""Read NodeNorm request logs out of whatever log exports are in a directory.

Since NodeNormalization#312, NodeNorm logs one line per `get_normalized_nodes` call:

    2025-06-18 07:26:30,635 | INFO | normalizer:get_normalized_nodes | Normalized 1 nodes
    in 1.21 ms with arguments (curies=['UMLS:C0132098'], conflate_gene_protein=True, ...)

`iter_requests()` walks a directory, reads every file it has a reader for, and yields one
parsed request per distinct log line. `load_logs()` collects those into columns for a
DataFrame, with a `FileSummary` per file saying what was read and what was skipped.

Standard library only. The one reader so far is for Loki exports (the Sterling
`loki_query_results_*.json` files), loose or inside a tar archive. To support another
source, add a branch to `_read_member()` that yields `(line, pod, node_name, namespace,
entry_id)`, where `entry_id` is whatever the source has that tells two log entries apart.

Log files are untrusted input: they are sent to us, and the CURIEs in them were typed by
whoever called the service. So nothing is extracted to disk, the regexes have no adjacent
quantifiers that could match the same text, and anything from a file that reaches a
message is truncated and `repr()`-escaped.
"""

import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator, NamedTuple, Optional

# Requests at least this slow keep a preview of their CURIEs, for the slow-request table.
SLOW_REQUEST_MS = 1000.0
CURIES_PREVIEW_LENGTH = 200

# Anchored on the literal text between the fields, so no two quantifiers compete. Matched
# with search(), because some sources prefix the line with their own timestamp and a tab.
#
# The count and the time come before the arguments, so a line a log shipper truncated
# still parses; only its options are lost.
_REQUEST_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) \| INFO \| normalizer:get_normalized_nodes \| "
    r"Normalized (\d+) nodes in (\d+(?:\.\d+)?) ms with arguments \(curies=\["
)
_OPTIONS_RE = re.compile(r"(?:\w+=\w+, )*\w+=\w+\)")
_FIRST_PREFIX_RE = re.compile(r"'([^':]{1,40}):")
# ponytail: a CURIE containing an apostrophe is logged in double quotes and is missed
# here. Parse the list with ast.literal_eval if those ever matter; it is ~40x slower.
_CURIE_RE = re.compile(r"'([^']*)'")

_TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar")


class ParsedRequest(NamedTuple):
    time: str  # "YYYY-MM-DD HH:MM:SS.mmm", UTC, as NodeNorm logged it
    curie_count: int
    time_taken_ms: float
    options: Optional[
        str
    ]  # "conflate_gene_protein=True, ..."; None if the line was cut short
    first_prefix: str  # prefix of the first CURIE, "" if it has none
    curies_text: str  # the inside of the logged list: "'A:1', 'B:2'"


def parse_log_line(line: str) -> Optional[ParsedRequest]:
    """Parse one log line, or return None if it is not a get_normalized_nodes line.

    An earlier version parsed the arguments with `ast`, which cost ~87µs a line (seven
    minutes for the 4.8M lines of three months of logs) and so had to drop any line over
    49,151 characters. Those are the largest batches, which matter most for performance.
    """
    match = _REQUEST_RE.search(line)
    if not match:
        return None
    rest = line[match.end() :]

    # The options follow the last "], ". If what follows is not a clean list of
    # name=value pairs, the line was truncated somewhere inside the CURIEs.
    options = None
    curies_text = rest
    list_end = rest.rfind("], ")
    if list_end != -1 and _OPTIONS_RE.fullmatch(rest, list_end + 3):
        options = rest[list_end + 3 : -1]
        curies_text = rest[:list_end]

    prefix = _FIRST_PREFIX_RE.match(rest)
    return ParsedRequest(
        time=f"{match.group(1)}.{match.group(2)}",
        curie_count=int(match.group(3)),
        time_taken_ms=float(match.group(4)),
        options=options,
        first_prefix=prefix.group(1) if prefix else "",
        curies_text=curies_text,
    )


def curies_in(curies_text: str) -> list[str]:
    """The CURIEs in a ParsedRequest's curies_text."""
    return _CURIE_RE.findall(curies_text)


NS_PER_HOUR = 3_600_000_000_000


def merge_windows(windows) -> list:
    """Merge overlapping or touching (start, end) windows into a sorted, disjoint list."""
    merged = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


@dataclass
class FileSummary:
    """What was read from one file in the log directory."""

    path: str  # relative to the log directory
    size_bytes: int
    format: str = ""
    members_read: int = 0  # files read: 1 for a loose file, many for an archive
    skipped: Counter = field(default_factory=Counter)  # reason -> number of files
    requests: int = 0
    curies: int = 0
    first_request: str = ""
    last_request: str = ""
    # (start, end) of every query the export says it ran, in nanoseconds since the epoch.
    # These say which periods were asked for, so an hour with no requests can be told
    # apart from an hour nobody downloaded.
    windows: list = field(default_factory=list)
    duplicates: int = 0  # log entries already seen, in this file or an earlier one
    other_lines: int = 0  # lines that are not get_normalized_nodes lines
    error: str = ""

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        if self.members_read:
            return "loaded"
        return "skipped"

    @property
    def hours_queried(self) -> float:
        """Hours the export's queries cover, counting an overlap once."""
        return (
            sum(end - start for start, end in merge_windows(self.windows)) / NS_PER_HOUR
        )

    @property
    def notes(self) -> str:
        notes = [f"error: {self.error}"] if self.error else []
        notes += [
            f"{count:,} skipped: {reason}"
            for reason, count in self.skipped.most_common()
        ]
        return "; ".join(notes)


def _is_loki_export(parsed) -> bool:
    """A Loki export is a list of [query, response] pairs, one per page of results."""
    return isinstance(parsed, list) and all(
        isinstance(item, list)
        and len(item) == 2
        and isinstance(item[0], dict)
        and "start" in item[0]
        and "end" in item[0]
        and isinstance(item[1], dict)
        for item in parsed
    )


def _read_member(
    name: str, fileobj: IO[bytes], summary: FileSummary
) -> Iterator[tuple]:
    """Yield (line, pod, node_name, namespace, entry_id) from one file, chosen by its name."""
    lowered = name.lower()
    if lowered.endswith(".json"):
        try:
            parsed = json.load(fileobj)
        except ValueError:
            summary.skipped["not valid JSON"] += 1
            return
        if not _is_loki_export(parsed):
            summary.skipped["JSON, but not a Loki export"] += 1
            return
        summary.members_read += 1
        for query, response in parsed:
            summary.windows.append((int(query["start"]), int(query["end"])))
            for stream in response["data"]["result"]:
                labels = stream["stream"]
                pod = str(labels.get("pod", ""))
                node_name = str(labels.get("node_name", ""))
                namespace = str(labels.get("namespace", ""))
                for timestamp, line in stream["values"]:
                    yield line, pod, node_name, namespace, timestamp
    elif lowered.endswith(".csv"):
        # The Sterling exports write every query as both .json and .csv. Only the JSON
        # records the query window, so that is the one we read.
        summary.skipped["CSV twin of a JSON export"] += 1
    else:
        suffix = Path(lowered).suffix or "(none)"
        summary.skipped[f"no reader for {suffix[:12]!r} files"] += 1


def _read_file(path: Path, summary: FileSummary) -> Iterator[tuple]:
    if path.name.lower().endswith(_TAR_SUFFIXES):
        summary.format = "tar archive"
        # "r|*" streams the archive: members are read in order and never written to disk.
        with tarfile.open(path, "r|*") as tar:
            for member in tar:
                if member.isfile():
                    yield from _read_member(
                        member.name, tar.extractfile(member), summary
                    )
    else:
        with open(path, "rb") as fileobj:
            yield from _read_member(path.name, fileobj, summary)
        summary.format = "Loki JSON" if summary.members_read else ""


def iter_requests(log_dir, summaries: Optional[list] = None) -> Iterator[tuple]:
    """Yield (ParsedRequest, pod, node_name, namespace, source) for every distinct request.

    Every file under `log_dir` is visited, in sorted order; `source` is its path relative
    to `log_dir`. A FileSummary per file is appended to `summaries` if one is given.

    A log entry seen before (same pod, same Loki timestamp, same text) is dropped: Loki's
    pages overlap by a few rows, and this also makes it harmless to drop in two exports
    that cover the same period. The text alone is not enough to go on: a pod does log the
    same request, with the same timing, twice within a millisecond.

    A file that cannot be read is recorded as an error on its summary and the walk goes
    on, so one bad archive does not hide the rest. Check `FileSummary.status`.
    """
    log_dir = Path(log_dir)
    # ponytail: one 64-bit hash per request (~300MB for 5M), so a collision is possible in
    # principle. Keep the (pod, timestamp) pairs themselves if the logs outgrow this.
    seen = set()
    for path in sorted(p for p in log_dir.rglob("*") if p.is_file()):
        if any(part.startswith(".") for part in path.relative_to(log_dir).parts):
            continue
        source = str(path.relative_to(log_dir))
        summary = FileSummary(path=source, size_bytes=path.stat().st_size)
        if summaries is not None:
            summaries.append(summary)
        try:
            for line, pod, node_name, namespace, entry_id in _read_file(path, summary):
                request = parse_log_line(line)
                if request is None:
                    summary.other_lines += 1
                    continue
                key = hash((pod, entry_id, line))
                if key in seen:
                    summary.duplicates += 1
                    continue
                seen.add(key)
                summary.requests += 1
                summary.curies += request.curie_count
                if not summary.first_request or request.time < summary.first_request:
                    summary.first_request = request.time
                if request.time > summary.last_request:
                    summary.last_request = request.time
                yield request, pod, node_name, namespace, source
        except (
            OSError,
            EOFError,
            tarfile.TarError,
            KeyError,
            TypeError,
            ValueError,
        ) as e:
            summary.error = f"{type(e).__name__}: {str(e)[:200]!r}"


@dataclass
class LoadedLogs:
    columns: dict  # column name -> list, one entry per request
    files: list  # FileSummary, one per file found


def load_logs(log_dir) -> LoadedLogs:
    """Load every request under `log_dir` into columns, ready for `pandas.DataFrame`.

    The CURIEs themselves are not kept, only their count and the first one's prefix:
    three months of logs name 84M of them. Use `count_curies()` for CURIE-level questions.
    """
    names = (
        "time curie_count time_taken_ms options pod node_name namespace first_prefix source curies_preview"
    ).split()
    columns = {name: [] for name in names}
    appends = [columns[name].append for name in names]
    shared = {}  # one string object per distinct options/prefix value, not one per row
    files = []
    for request, pod, node_name, namespace, source in iter_requests(log_dir, files):
        slow = request.time_taken_ms >= SLOW_REQUEST_MS
        row = (
            request.time,
            request.curie_count,
            request.time_taken_ms,
            shared.setdefault(request.options, request.options),
            pod,
            node_name,
            namespace,
            shared.setdefault(request.first_prefix, request.first_prefix),
            source,
            request.curies_text[:CURIES_PREVIEW_LENGTH] if slow else "",
        )
        for append, value in zip(appends, row):
            append(value)
    return LoadedLogs(columns=columns, files=files)


def count_curies(log_dir) -> Counter:
    """Count how often each CURIE was asked for, across every request under `log_dir`.

    ponytail: holds every distinct CURIE as a string (16M in one month of dev logs, a few
    GB). Count 64-bit hashes in a numpy array instead if this stops fitting in memory.
    """
    counts = Counter()
    for request, *_ in iter_requests(log_dir):
        counts.update(curies_in(request.curies_text))
    return counts
