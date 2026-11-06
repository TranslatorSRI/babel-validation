# Investigating NodeNorm ES against NodeNorm Redis

Regression tests for bugs filed against the Elasticsearch-backed NodeNorm
(`biothings/NodeNormalizationAPI`, formerly `biothings/pending.api`) live here, one file per
issue. This file records what was learned while investigating them, so that the next
comparison starts from here rather than from scratch. The 2026-09-29 investigation (Evan's
ORION build on ITRB against ES normalized differently from his RENCI build against Redis;
issues #40 and #41) is the worked example.

**A test that passes while its issue is still open means the issue looks fixed.** That
includes a strict-xfail test reporting XPASS on an ES target. Recommend to the operator that
they close the issue, citing the passing run: the targets, their `/status` `version` and
`babel_version`, and the commit tested. Don't close it yourself; the issue belongs to the
biothings maintainers. Closing is not the same as deploying: #40 and #41 were closed while
`ci` still served the old code, so their xfail markers stay until the XPASS shows the fix
has reached every ES target. Then take the marker out and keep the test as a regression
guard, as `test_issue_10.py` and `test_issue_14.py` are.

## Which deployment is which

`/status` says everything you need: `backend`, `babel_version`, `version`. Check it first,
because the ES deployments do not all track the same Babel release. On 2026-11-06:

| target | backend | Babel | notes |
|---|---|---|---|
| `ci` | elasticsearch 1.2.0 | 2026jul22 | the ES instance ORION builds against |
| `test` | elasticsearch 1.2.0 | 2025sep1 | one release behind `ci` |
| `prod` | elasticsearch 1.0.0 | 2025sep1 | moved from Redis in #154 |
| `dev`, `exp` | redis 2.5.1 | 2026jul22 | the Redis comparison point for `ci` |

So "same Babel release, different backend" is `ci` vs `dev`. Both backends' `/status`
report `backend`; ES's also reports the ES cluster.

## Where the ES code is

- **API**: `biothings/NodeNormalizationAPI`, `src/nodenorm/handlers/normalized_nodes.py`.
  `_lookup_equivalent_identifiers()` is one size-1 `msearch` per CURIE on `identifiers.i`;
  `_populate_biolink_type_ancestors()` expands the document's `type` with BMT.
- **Loader** (a BioThings data plugin): `plugins/nodenorm/{static,dumper,worker,uploader}.py`
  in *both* `biothings/pending.api` (last touched 2025-11) and `biothings/annotation-hub`
  (actively developed, 2026-07/08, with a `MEMORY_INVESTIGATION.md`). `static.py` is the same
  in both and hard-codes the compendium file list (#40). `worker.py` resolves a duplicate
  `_id` with `biothings.utils.dataload.merge_struct`, which is what turns `type` into a list
  (#41). The plugin `README.md` documents their duplicate-CURIE handling ("case 1/2/3").
- Issues go to `biothings/NodeNormalizationAPI` even when the defect is in the plugin; the
  earlier pending.api ones (#338) were consolidated there.

The ES service exposes only `/status`, `/get_normalized_nodes`, `/get_setid`,
`/get_semantic_types` and `/get_allowed_conflations`: there is no raw-document or query
endpoint, so what the index holds has to be inferred from API output. Two signatures:

- **`null` on ES, a clique on Redis** for the same Babel release: the compendium the clique
  lives in was not loaded (#40). Confirm by finding which `compendia/*.txt` file holds the
  CURIE.
- **`biolink:NamedThing` twice, or `biolink:Entity` anywhere, in `type`**: the document's
  `type` is a list, i.e. two compendia's documents were merged (#41). The order of the
  concatenated ancestor lists is the load order, so `type[0]` can flip category too.

## Babel's outputs are public

`https://stars.renci.org/var/babel_outputs/<release>/`:

- `compendia/*.txt` — one JSON clique per line. Sizes for 2026jul22: `Food.txt` 89 KB,
  `Cell.txt` 4 MB, `ChemicalEntity.txt` 91 MB, `AnatomicalEntity.txt` 40 MB, `umls.txt`
  322 MB, `OrganismTaxon.txt` 737 MB, `Protein.txt` 47 GB. Everything but Protein, Gene,
  SmallMolecule, MolecularMixture and Publication downloads in seconds;
  `grep '"i": "MESH:C469385"' ChemicalEntity.txt` then answers "is this CURIE in that
  compendium, and does it lead the clique".
- `reports/duckdb/duplicate_clique_leaders.tsv` (600 KB) — every CURIE that is the clique
  *leader* in two or more compendia, with `filenames`, `biolink_types` and the size of each
  clique. This is exactly the #41 case (a duplicate `_id` in the ES upload): 7,571 rows in
  2026jul22, 6,600 of them yeast ENSEMBL Gene+Protein and 891 MeSH ChemicalEntity+Protein.
  Start here, not with the wider file below. The Babel issues per slice: #276 is the
  umbrella, #39 the yeast ENSEMBL ids (singletons in both compendia), #308 protein versus
  chemical, #1123 taxon versus anatomy or chemical.
- `reports/duckdb/duplicate_curies.tsv` (2.4 MB) — every CURIE in more than one compendium,
  leader or not, with `clique_leaders` and `filenames` columns. A CURIE that is a member of
  two cliques but leads at most one becomes two ES documents, and the API returns the first
  hit. Note the `filenames` column in both files is an unquoted `[A, B]` list, so
  `ast.literal_eval` fails on it; split on commas.
- `reports/umls/duplicate-curies.csv` — the UMLS subset, analysed in Babel #308.
- The Babel repo's `releases/<release>/` keeps the release notes and summary tables, not
  the compendia or these reports.

The Redis loader (`NodeNormalization/node_normalizer/loader/loader.py`) writes each CURIE
with a plain `SET`, so for a duplicated CURIE the last compendium loaded wins: arbitrary,
but always one real clique.

## Finding example CURIEs

NameRes takes a type filter and a prefix filter, which is the quickest way to get a batch of
candidates of a given shape:

```
https://name-resolution-sri.renci.org/lookup?string=virus&biolink_type=biolink:OrganismTaxon&only_prefixes=MESH&limit=100
```

Two caveats. `limit` needs a real query string (`string=a` returns an error, not a list).
And for a duplicated CURIE NameRes's own `types` can disagree with NodeNorm Redis — Solr
also keeps whichever copy was indexed last — so a NameRes hit typed ChemicalEntity that
NodeNorm calls Protein is itself evidence of a duplicate, not a NameRes bug.

## Reading an ORION schema diff

Evan's comparison files (`data/nodenorm-discrepency-2026sep29/`, not committed) are ORION's
graph metadata for each build plus a `schema-diff` between them. `diff.nodes` is one entry
per *category combination* (the set of leaf Biolink categories ORION derived from NodeNorm's
`type` list) with old/new counts and `id_prefixes` deltas. A combination that is new in the
ES build and whose prefixes are all `MESH` is the #41 signature; a combination that dropped
to zero is a compendium that was not loaded (#40). The counts per combination matched the
compendium pairs in Babel's `duplicate_clique_leaders.tsv` almost one for one, which is what tied
the two together.
