# What already exists

## Threads this builds on

- **#149 — replace the sheet with a YAML file in this repo.** Whatever record format it picks
  is the crux for everything here (see the next section). It leaves open how it relates to
  the issue assertions and to `csv-to-babeltests`, and what to do about the blocklist sheet,
  which may not be public.
- **#77 / #104 — `csv-to-babeltests`.** Turns a collaborator's CSV into a `babel_tests` block
  for an issue; emits only HasLabel, ResolvesWithType and ResolvesWith. Retargeted to emit
  #149's record format, it is the one-off importer this plan needs. #78 and #79 are follow-ups
  (fill in CURIEs from labels; refresh stale CURIEs).
- **#100 — factor BabelTest parsing out of GitHub fetching**, "only if we move to a file or
  database source". A file source makes it necessary.
- **#136 — per-target expectations** for issue assertions. **#138 — expected rank.**
- **#35 — the Translator Test Harness data.** See below: it is public, and it is the first
  real external source.
- **#65 — overall design**, including a web frontend for running tests and triaging, which
  overlaps the workspace idea.
- **#126** — what a secret sheet ID costs: both sheets had to be re-shared under new IDs after
  the old ones sat in public history.
- **Babel #573** (where the issue syntax came from; the contributor guide is Babel's
  `docs/Triage.md`) and **Babel #916** (run the issue tests inside Babel's own build).

## What the sheet can say that the eight issue assertions cannot

The sheet-driven tests (`tests/nodenorm/test_nodenorm_from_gsheet.py`,
`tests/nameres/test_nameres_from_gsheet.py`, over `src/babel_validation/core/testrow.py`)
express expectations the issue handlers in `src/babel_validation/assertions/` have no way to
carry:

| Sheet expectation | Nearest issue assertion | Gap |
|---|---|---|
| Conflation mode (`gene_protein`, `drug_chemical`) | none | Conflation is a query *parameter*; every handler normalizes with none |
| A *specific* preferred clique ID | `ResolvesWith` | Only checks that CURIEs share a clique, relative to the first resolvable param |
| Excluded Biolink type (`!type`) | `ResolvesWithType` | Presence only |
| Label match | `HasLabel` | Case-sensitive; the sheet compares case-insensitively |
| NameRes autocomplete, `biolink_type` filter, only/exclude prefixes | `SearchByName` | Fixed params: `autocomplete=false`, `limit=5` |
| Negative lookup (CURIE must *not* be in the top N) | none | |
| Top-hit label | none | |
| Top-1 with an xfail band up to rank 5 | `SearchByName` | Passes anywhere in the top 5 |
| Expected pass/fail per service, as strict xfail | open/closed issue state | One state per issue, not per service or per search mode |
| Provenance: Category, Source, Source URL | the issue itself | |

So a records file needs its own executor, grown from the two `*_from_gsheet.py` tests. Sharing
handlers with the issue harness is a later unification, and it overlaps #136 and #138 — it is
not a free consequence of choosing a format.

## The Translator Tests repository (#35)

#35 assumed the Test Harness data was behind a private link. It is not:
[`NCATSTranslator/Tests`](https://github.com/NCATSTranslator/Tests) is public, and its
`test_assets/` holds 657 `Asset_N.json` files, each with `input_name`, `input_id`,
`input_category`, the same three for `output_*`, a stable `id`, and a
`test_metadata.test_reference` that is usually a Feedback issue. That is roughly 1,300
name → CURIE → Biolink-type triples with provenance, maintained by another team, in their own
repo, in their own format.

Two things follow:

- **"Federation" is not "everyone writes our YAML".** The first real external source needs an
  adapter. The design has to have a `format` per source from the start.
- **An adapter must be honest about what it can derive.** `input_name` → top hit `input_id` is
  a genuine NameRes test. "`input_id` has type `input_category`" is a real check. But
  "`input_id` normalizes to itself" is circular if NodeNorm produced those IDs in the first
  place (unverified, but that is how the Test Harness pipeline works) — a regression guard, not
  a correctness test. And a label assertion is *not* derivable, because `input_name` may be a
  synonym rather than Babel's preferred label.

Their assets are edge-shaped (subject, predicate, object); ours are node-shaped. That is why
importing from them makes more sense than adopting their format.
