"""Generate assertions/README.md from handler class attributes.

Run:
    uv run python -m src.babel_validation.assertions.gen_docs
"""

from pathlib import Path

from src.babel_validation.assertions import (
    ASSERTION_HANDLERS, AssertionHandler, NodeNormTest, NameResTest,
)

README_PATH = Path(__file__).parent / "README.md"

INTRO = """\
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

---
"""

ADDING_NEW = """\
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

3. Implement `test_params_list()` (or both `test_with_*` methods for `AssertionHandler`
   subclasses). It receives one params_list at a time, already stripped and — unless the
   handler sets `VALIDATE_CURIES = False` — with its CURIEs validated and pre-warmed in
   the NodeNorm cache. Yield one result per thing checked, usually one per CURIE, so a
   failure names the CURIE that failed. Override `curie_params()` if some params are not
   CURIEs; see `HasLabel` and `SearchByName`.

4. Import it in `__init__.py` and add an instance to `ASSERTION_HANDLERS`. Order does not
   matter — this file groups handlers by the service they test.

5. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate `README.md`,
   and `uv run pytest -m unit` to confirm the checked-in copy is in sync.
"""

_GROUP_HEADERS: dict[str, str] = {
    "NodeNorm": (
        "## NodeNorm Assertions\n\n"
        "These assertions test the [NodeNorm](https://nodenorm.transltr.io/docs) service."
    ),
    "NameRes": (
        "## NameRes Assertions\n\n"
        "These assertions test the [NameRes](https://name-lookup.transltr.io/docs) service."
    ),
    "NodeNorm and NameRes": "## Special Assertions",
}


def _display_name(h: AssertionHandler) -> str:
    """The assertion name as written in issues (ResolvesHandler -> "Resolves").

    Derived from the class name rather than NAME, which is lowercased for
    case-insensitive matching and so reads poorly as a heading.
    """
    return type(h).__name__.removesuffix("Handler")


def _applies_to(h: AssertionHandler) -> str:
    """Which service(s) this handler tests; also the key into _GROUP_HEADERS.

    A handler that subclasses neither base overrides the test_with_* methods
    directly and so applies to both.
    """
    if isinstance(h, NodeNormTest):
        return "NodeNorm"
    if isinstance(h, NameResTest):
        return "NameRes"
    return "NodeNorm and NameRes"


def _render_handler(h: AssertionHandler) -> str:
    """Render one handler's README section from its documentation attributes.

    Reads them with getattr defaults so that a handler missing one still renders
    (as an empty section) instead of breaking the whole README.
    """
    name = _display_name(h)
    service = _applies_to(h)
    description = getattr(h, "DESCRIPTION", "")
    parameters = getattr(h, "PARAMETERS", "")
    wiki_examples = getattr(h, "WIKI_EXAMPLES", [])
    yaml_params = getattr(h, "YAML_PARAMS", "")

    parts = []
    parts.append(f"### {name}\n")
    parts.append(f"**Applies to:** {service}\n")
    parts.append(f"{description}\n")

    if parameters:
        parts.append(f"**Parameters:** {parameters}\n")

    wiki_block = "\n".join(wiki_examples)
    parts.append(f"**Wiki syntax:**\n```\n{wiki_block}\n```\n")

    parts.append(
        f"**YAML syntax:**\n```yaml\nbabel_tests:\n  {name}:\n{yaml_params}\n```\n"
    )

    parts.append("---\n")

    return "\n".join(parts)


def generate_readme() -> str:
    """Render the complete README.md content. Pure — writing it is the caller's job.

    Kept side-effect free so test_assertions_docs.py can compare the rendered
    output against the checked-in file without touching the filesystem.
    """
    sections = [INTRO]

    # Group by service rather than by registration order, so a handler added
    # anywhere in ASSERTION_HANDLERS still renders under the right heading.
    for service, header in _GROUP_HEADERS.items():
        handlers = [h for h in ASSERTION_HANDLERS.values() if _applies_to(h) == service]
        if not handlers:
            continue
        sections.append(header + "\n")
        sections.extend(_render_handler(h) for h in handlers)

    sections.append(ADDING_NEW)
    return "\n".join(sections)


if __name__ == "__main__":
    content = generate_readme()
    README_PATH.write_text(content, encoding="utf-8")
    print(f"Written to {README_PATH}")
