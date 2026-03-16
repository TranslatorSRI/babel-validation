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

**YAML syntax** (multiple assertions, multiple param sets):
````
```yaml
babel_tests:
  AssertionType:
    - param1
    - [param1, param2]
```
````

Assertion names are case-insensitive.

## Param Sets

Each assertion can be invoked with one or more **param sets** — independent groups of
parameters that are each evaluated separately.

- **Wiki syntax** — each `{{BabelTest|...}}` line is one param set.
- **YAML syntax** — each list entry under an assertion key is one param set; a bare string
  is a single-element param set, a YAML list is a multi-element param set.

The meaning of each element in a param set depends on the assertion type (see below).
For most assertions the elements are CURIEs; for `HasLabel` the second element is a
label string; for `ResolvesWithType` the first element is a Biolink type.

---

## NodeNorm Assertions

These assertions test the [NodeNorm](https://nodenorm.transltr.io/docs) service.

### Resolves

**Applies to:** NodeNorm

Each CURIE in each param_set must resolve to a non-null result in NodeNorm.

**Parameters:** One or more CURIEs per param_set.

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

Each CURIE in each param_set must fail to resolve (return null) in NodeNorm. Use this to confirm that an identifier is intentionally not normalizable.

**Parameters:** One or more CURIEs per param_set.

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

All CURIEs within each param_set must resolve to the identical normalized result. Use this to assert that two identifiers are equivalent.

**Parameters:** Two or more CURIEs per param_set. All must resolve to the same result.

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

The CURIEs within each param_set must NOT all resolve to the same normalized result. Use this to assert that two identifiers are intentionally distinct entities.

**Parameters:** Two or more CURIEs per param_set. They must not all resolve to the same result.

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

**Parameters:** Exactly two elements per param_set: a CURIE, then the expected label string.

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

Each param_set must have at least two elements: the first is the expected Biolink type (e.g. 'biolink:Gene'), and the remainder are CURIEs that must resolve with that type.

**Parameters:** Each param_set: first element is the expected Biolink type (e.g. `biolink:Gene`), remaining elements are CURIEs.

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

Each param_set must have at least two elements: a search query string and an expected CURIE. The test passes if the CURIE's normalized identifier appears within the top N results (default N=5) when NameRes looks up the search query.

**Parameters:** Each param_set: the **search query string** and the **expected CURIE**. The CURIE is normalized via NodeNorm (drug/chemical conflation enabled) before matching.

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
   - `nodenorm.py` — for NodeNorm-only assertions (subclass `NodeNormTest`, override `test_param_set`)
   - `nameres.py` — for NameRes-only assertions (subclass `NameResTest`, override `test_param_set`)
   - `common.py` — for assertions that apply to both services (subclass `AssertionHandler`, override `test_with_nodenorm` and/or `test_with_nameres`)

2. Define the class with `NAME`, `DESCRIPTION`, `PARAMETERS`, `WIKI_EXAMPLES`, `YAML_PARAMS`, and `test_param_set()` (or both `test_with_*` methods for `AssertionHandler` subclasses).

3. Import it in `__init__.py` and add an instance to `ASSERTION_HANDLERS`.

4. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate `README.md`.
