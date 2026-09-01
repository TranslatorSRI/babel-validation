<!-- AUTO-GENERATED — do not edit by hand.
     Regenerate with: uv run python -m src.babel_validation.assertions.gen_docs -->

# BabelTest Assertion Types

This package defines the assertion types that can be embedded in GitHub issue bodies and evaluated against the NodeNorm and NameRes services.

## Embedding Tests in Issues

Two syntaxes are supported:

**Wiki syntax** (one assertion per line):
```
{{BabelTest|AssertionType|param1|param2|...}}
```

**YAML syntax** (multiple assertions, multiple params lists):
````
```yaml
babel_tests:
  AssertionType:
    - param1
    - [param1, param2]
```
````

Assertion names are case-insensitive, as is the `{{BabelTest|...}}` marker itself.

## Params Lists

Each assertion can be invoked with one or more **params lists** — independent groups of
parameters that are each evaluated separately.

- **Wiki syntax** — each `{{BabelTest|...}}` line is one params list.
- **YAML syntax** — each list entry under an assertion key is one params list; a bare string
  is a single-element params list, a YAML list is a multi-element params list.

The meaning of each element in a params list depends on the assertion type (see below).
For most assertions the elements are CURIEs; for `HasLabel` the second element is a
label string; for `ResolvesWithType` the first element is a Biolink type.

## Limits

Issue bodies are untrusted input — anyone can write one, and nothing reviews it before the
harness parses it and turns it into live NodeNorm and NameRes calls. These caps bound what
one issue can cost. They sit far above anything a real issue contains:

| Limit | Value |
| --- | --- |
| Assertions per issue | 100 |
| Params lists per issue | 1,000 |
| Parameters per issue | 1,000 |
| Characters per parameter | 1,000 |

Exceeding one of the first three fails the whole issue rather than running part of it — split
the assertions across several issues. An individual parameter that is too long, empty, or
contains non-printable characters fails only its own params list; the rest of the issue still
runs.

YAML anchors and aliases (`&name` / `*name`, including merge keys) are rejected: they let a few
hundred bytes expand into megabytes. Duplicate keys in a `babel_tests` block are rejected too,
since YAML would silently keep only the last one — and then the block a reviewer reads would
not be the one that runs.

---

## NodeNorm Assertions

These assertions test the [NodeNorm](https://nodenorm.transltr.io/docs) service.

### Resolves

**Applies to:** NodeNorm

Each CURIE in each params_list must resolve to a non-null result in NodeNorm.

**Parameters:** One or more CURIEs per params_list.

**Wiki syntax:**
```
{{BabelTest|Resolves|CHEBI:15365}}
{{BabelTest|Resolves|MONDO:0005015|DOID:9351}}
```

**YAML syntax:**
```yaml
babel_tests:
  Resolves:
    - CHEBI:15365
    - [MONDO:0005015, DOID:9351]
```

---

### DoesNotResolve

**Applies to:** NodeNorm

Each CURIE in each params_list must fail to resolve (return null) in NodeNorm. Use this to confirm that an identifier is intentionally not normalizable.

**Parameters:** One or more CURIEs per params_list.

**Wiki syntax:**
```
{{BabelTest|DoesNotResolve|FAKENS:99999}}
```

**YAML syntax:**
```yaml
babel_tests:
  DoesNotResolve:
    - FAKENS:99999
```

---

### ResolvesWith

**Applies to:** NodeNorm

All CURIEs within each params_list must resolve to the identical normalized result. Use this to assert that two identifiers are equivalent.

**Parameters:** Two or more CURIEs per params_list. All must resolve to the same result.

**Wiki syntax:**
```
{{BabelTest|ResolvesWith|CHEBI:15365|PUBCHEM.COMPOUND:1}}
```

**YAML syntax:**
```yaml
babel_tests:
  ResolvesWith:
    - [CHEBI:15365, PUBCHEM.COMPOUND:1]
    - [MONDO:0005015, DOID:9351]
```

---

### DoesNotResolveWith

**Applies to:** NodeNorm

The CURIEs within each params_list must NOT all resolve to the same normalized result. Use this to assert that two identifiers are intentionally distinct entities.

**Parameters:** Two or more CURIEs per params_list. They must not all resolve to the same result.

**Wiki syntax:**
```
{{BabelTest|DoesNotResolveWith|CHEBI:15365|CHEBI:16856}}
```

**YAML syntax:**
```yaml
babel_tests:
  DoesNotResolveWith:
    - [CHEBI:15365, CHEBI:16856]
```

---

### HasLabel

**Applies to:** NodeNorm

The CURIE must resolve in NodeNorm and its primary label (id.label) must match the expected label exactly (case-sensitive).

**Parameters:** Exactly two elements per params_list: a CURIE, then the expected label string.

**Wiki syntax:**
```
{{BabelTest|HasLabel|CHEBI:15365|aspirin}}
```

**YAML syntax:**
```yaml
babel_tests:
  HasLabel:
    - [CHEBI:15365, aspirin]
```

---

### ResolvesWithType

**Applies to:** NodeNorm

Each params_list must have at least two elements: the first is the expected Biolink type (e.g. 'biolink:Gene'), and the remainder are CURIEs that must resolve with that type.

**Parameters:** Each params_list: first element is the expected Biolink type (e.g. `biolink:Gene`), remaining elements are CURIEs.

**Wiki syntax:**
```
{{BabelTest|ResolvesWithType|biolink:Gene|NCBIGene:1}}
```

**YAML syntax:**
```yaml
babel_tests:
  ResolvesWithType:
    - [biolink:Gene, NCBIGene:1, HGNC:5]
```

---

## NameRes Assertions

These assertions test the [NameRes](https://name-lookup.transltr.io/docs) service.

### SearchByName

**Applies to:** NameRes

Each params_list must have exactly two elements: a search query string and an expected CURIE. The test passes if the CURIE's normalized identifier appears within the top N results (default N=5) when NameRes looks up the search query.

**Parameters:** Each params_list: the **search query string** and the **expected CURIE**. The CURIE is normalized via NodeNorm before matching.

**Wiki syntax:**
```
{{BabelTest|SearchByName|water|CHEBI:15377}}
```

**YAML syntax:**
```yaml
babel_tests:
  SearchByName:
    - [water, CHEBI:15377]
    - [diabetes, MONDO:0005015]
```

---

## Special Assertions

### Needed

**Applies to:** NodeNorm and NameRes

Marks an issue as needing a test — always fails as a reminder to add real assertions.

**Wiki syntax:**
```
{{BabelTest|Needed}}
```

**YAML syntax:**
```yaml
babel_tests:
  Needed:
    - placeholder
```

---

## Adding a New Assertion Type

1. Choose the right module:
   - `nodenorm.py` — for NodeNorm-only assertions (subclass `NodeNormTest`, override `test_params_list`)
   - `nameres.py` — for NameRes-only assertions (subclass `NameResTest`, override `test_params_list`)
   - `common.py` — for assertions that apply to both services (subclass `AssertionHandler`, override `test_with_nodenorm` and/or `test_with_nameres`)

2. Give the class its five documentation attributes:
   - `NAME` — **must be all lowercase.** Assertions are matched case-insensitively by
     lowercasing whatever the issue wrote, so a `NAME` containing any uppercase could
     never be matched. Registration rejects it rather than letting it fail silently.
   - `DESCRIPTION` — one line, shown under the heading here.
   - `PARAMETERS` — what each element of a params_list means, and how many are expected.
   - `WIKI_EXAMPLES` — complete `{{BabelTest|...}}` lines, reproduced verbatim.
   - `YAML_PARAMS` — indented list entries for the YAML example.

   These are rendered into this file, so write them for someone reading this README
   rather than for someone reading the class.

3. Declare how many params a params_list may have with `MIN_PARAMS` and `MAX_PARAMS`
   (default: one or more). Arity is checked during preparation, so a params_list of the
   wrong length is rejected before any CURIE is looked up and `test_params_list()` never
   sees it — do not re-check it by hand.

4. Implement `test_params_list()` (or both `test_with_*` methods for `AssertionHandler`
   subclasses). It receives one params_list at a time, of a length you declared, already
   stripped and — unless the handler sets `VALIDATE_CURIES = False` — with its CURIEs
   validated and pre-warmed in the NodeNorm cache, so you can index into it directly.
   Yield one result per thing checked, usually one per CURIE, so a failure names the CURIE
   that failed. Override `curie_params()` if some params are not CURIEs; see `HasLabel`
   and `SearchByName`.

5. Import it in `__init__.py` and add an instance to `ASSERTION_HANDLERS`. Order does not
   matter — this file groups handlers by the service they test.

6. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate `README.md`,
   and `uv run pytest -m unit` to confirm the checked-in copy is in sync.
