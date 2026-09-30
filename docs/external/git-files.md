# Option 1: git files as the source of truth

"Contributors keep test files in their own repos and we link to them" turned out to be four
mechanisms, and the one that phrase suggests is the least attractive.

## (a) Directories in this repo, owned by the contributing team

`sources/<team>/records.yaml`, with a `CODEOWNERS` line so a PR touching it needs their review
and ours. One loader, one review surface, no fetch at test time, no token, no cache. #149's
file is the first directory. This is federation for anyone willing to open a pull request,
which is probably most of the contributors we will actually get.

## (b) A SHA-pinned git submodule plus an adapter

For a source that owns its repo and its format — `NCATSTranslator/Tests` (#35) is the case in
hand. `actions/checkout` with `submodules: true` means there is no collection-time download at
all, which sidesteps the xdist hazard `CLAUDE.md` warns about (a fetch in
`pytest_generate_tests` runs once per worker, with no timeout, and a divergence aborts the
run). Dependabot bumps the pin; the bump PR is where we see what changed; a force-pushed,
renamed or transferred upstream cannot change what we run.

The adapter derives records from their files. What it may honestly derive is in
[what-exists.md](what-exists.md).

## (c) A one-off import

`csv-to-babeltests` (#77, #104), retargeted to emit records, converts a spreadsheet into a
file once, as a pull request. The sheet is never fetched at test time. This is the distinction
that matters for Google Sheets: letting people *plug in* their own sheets was rightly rejected
— a runtime dependency on Google, a secret ID per sheet with all the never-log discipline that
implies (#126), no review, and validation of arbitrary spreadsheets — but *converting* a sheet
once is fine, and is how most "I have a spreadsheet" contributions should arrive.

## (d) A list of `org/repo@sha:path` in `targets.ini`, fetched at run time

What "federated repos" originally meant. It needs: a file-locked cache keyed on the SHA
(`fetch_sheet_csv()` is the pattern); a loud sentinel when a fetch fails, because a source
that 404s and collects zero tests looks like passing; a PAT for private repos, since the
workflow's `github.token` cannot read another org's private repo; `RawConfigParser`, because a
`%` in a path breaks `configparser` interpolation; and a list *separate* from `Repositories`,
which is the BabelTest issue crawl — reusing it would subscribe every data contributor's issue
tracker. (a)–(c) get the same result with none of that. Keep (d) in reserve for a source that
cannot be a submodule, such as a release asset with a checksum.

## Challenges all four share

**The trust boundary moves from "an issue" to "a file someone else wrote".** A SHA pin does
not make the content trusted: the maintainer bumping the pin cannot review the foreign diff
from our side. Every guard the issue loader has applies to the records loader regardless of
mechanism — the size cap before parsing, `_NoAliasSafeLoader`, the recursion limit, name and
CURIE shape checks, `_rejection()` as the one choke point, `%r` everywhere. Add caps that
**fail loudly rather than truncate**, per source *and* global: `dashboard.yaml` wraps each
target in a 45-minute timeout, so one 50,000-record source does not merely fail, it blanks
that whole environment's results.

**Ids are untrusted text.** The sheet uses `row=N` precisely so no cell reaches a pytest node
ID, an Actions log, a `?test=` URL or a `report.results` key. Records get harness-minted ids
(`source:N`, or an explicit `id:` constrained by a regex like the assertion-name one), and
everything is keyed on `(source, id)` because two sources will both have `id: 1`. Stable ids
matter for permalinks, `-k` selection and the overlay below — not for `history.jsonl`, which
only diffs per-target counts.

**Who owns red tests when the contributor is gone?** 624 of the sheet's rows came from one
contributor who is no longer around. When Babel legitimately changes, those rows go red in our
name. Two mechanisms, probably both:

- An **expectations overlay** in this repo: xfail-with-reason keyed on `(source, id)` plus a
  hash of the record's content, so an edited record invalidates its overlay entry instead of
  silently keeping it; failing hard on a key that matches no live record; with a stated
  precedence rule for when we and the contributor disagree. Local runs (`pytest
  --records path`) must apply it too, or a contributor's CI disagrees with the dashboard.
- **Non-strict xfail for foreign sources**, or expectations stamped with the Babel version
  they were recorded against, so a contributor's stale xfail becomes data rather than a daily
  strict-XPASS failure they are not around to fix.

**Contradictions and unsupported prefixes.** Two sources asserting different preferred IDs
for one CURIE means one is red forever and the harness cannot say which; a load-time
cross-source lint should report that as its own failing item (or "source #0 wins"). A source
asserting about a prefix Babel does not ingest fails as "could not normalize", indistinguishable
from a bug; `/get_curie_prefixes` (#66) lets that be classified separately, and per target,
because prefix support changes between Babel versions.

**A private source protects the file, not the run.** Even with details withheld the way
blocklist results are, the source's name leaks through `repos_allowlist` in the report,
through parametrize ids (the dashboard's `rowLabel` falls back to the raw key), and through
the public Actions log. A private source needs a PAT secret handled with the same never-log
discipline as the sheet ID, including redacting `requests` exception URLs. This is also the
honest answer to #149's open question about the blocklist sheet.

**The dashboard needs a new `kind`.** `generate_report.py` decides `kind` from the module
path and `:row=N`; a record is neither `gsheet` nor `issue`. The kind has to be threaded
through `Results.vue` (`ALL_KINDS`, `KIND_ORDER`, `KIND_HEADINGS`, which validate `?kinds=`)
and `reportData.js` (`rowLabel`; `isNodeNorm`, which picks service links by path prefix and
would mislabel a module that tests both services), and the source-URL allowlist has to admit
source repos.

**Load.** About 1,300 lookups a night for the Tests repo is nothing. A template repo whose CI
runs every push against dev is N teams hitting shared services. Chunk `normalize_curies`
(one POST today) and use the `CachedNodeNorm.from_url` singletons, which the gsheet tests
currently do not.
