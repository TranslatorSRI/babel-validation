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

---

## NodeNorm Assertions

These assertions test the [NodeNorm](https://nodenorm.transltr.io/docs) service.

### Resolves

**Applies to:** NodeNorm

Verifies that every CURIE in every param_set can be resolved to a non-null result.

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

Verifies that every CURIE in every param_set fails to resolve (returns null). Use this to confirm that an identifier is intentionally not normalizable.

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

Verifies that all CURIEs in a param_set resolve to the **identical** normalized result. Use this to assert that two or more identifiers are equivalent (same clique in NodeNorm).

**Parameters:** Two or more CURIEs per param_set. All must resolve and produce the same result.

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

### ResolvesWithType

**Applies to:** NodeNorm

Verifies that one or more CURIEs resolve with a specific Biolink type in their `type` list.

**Parameters:** Each param_set must have at least two elements. The **first** element is the expected Biolink type (e.g. `biolink:Gene`); the remaining elements are CURIEs to check.

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

Verifies that a name search returns an expected CURIE within the top-N results (default N=5).

The expected CURIE is first normalized via NodeNorm (with drug/chemical conflation enabled) to find its preferred identifier; that identifier must appear in the top results.

**Parameters:** Each param_set must have at least two elements: the **search query string** and the **expected CURIE**.

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

A placeholder that always fails. Use this on issues where you know a test is required but haven't written it yet.

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
   - `nodenorm.py` — for NodeNorm-only assertions (subclass `NodeNormAssertion`)
   - `nameres.py` — for NameRes-only assertions (subclass `NameResAssertion`)
   - `common.py` — for assertions that apply to both services (subclass `AssertionHandler`)

2. Define the class with `NAME`, `DESCRIPTION`, and the relevant `test_with_nodenorm()` / `test_with_nameres()` method(s).

3. Import it in `__init__.py` and add an instance to `ASSERTION_HANDLERS`.

4. Document it in this README.
