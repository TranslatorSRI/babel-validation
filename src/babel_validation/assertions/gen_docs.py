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
"""

ADDING_NEW = """\
## Adding a New Assertion Type

1. Choose the right module:
   - `nodenorm.py` — for NodeNorm-only assertions (subclass `NodeNormTest`, override `test_param_set`)
   - `nameres.py` — for NameRes-only assertions (subclass `NameResTest`, override `test_param_set`)
   - `common.py` — for assertions that apply to both services (subclass `AssertionHandler`, override `test_with_nodenorm` and/or `test_with_nameres`)

2. Define the class with `NAME`, `DESCRIPTION`, `PARAMETERS`, `WIKI_EXAMPLES`, `YAML_PARAMS`, and `test_param_set()` (or both `test_with_*` methods for `AssertionHandler` subclasses).

3. Import it in `__init__.py` and add an instance to `ASSERTION_HANDLERS`.

4. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate `README.md`.
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
    return type(h).__name__.removesuffix("Handler")


def _applies_to(h: AssertionHandler) -> str:
    if isinstance(h, NodeNormTest):
        return "NodeNorm"
    if isinstance(h, NameResTest):
        return "NameRes"
    return "NodeNorm and NameRes"


def _render_handler(h: AssertionHandler) -> str:
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
    sections = [INTRO]
    seen_groups: set[str] = set()

    for h in ASSERTION_HANDLERS.values():
        service = _applies_to(h)
        if service not in seen_groups:
            seen_groups.add(service)
            sections.append(_GROUP_HEADERS[service] + "\n")
        sections.append(_render_handler(h))

    sections.append(ADDING_NEW)
    return "\n".join(sections)


if __name__ == "__main__":
    content = generate_readme()
    README_PATH.write_text(content, encoding="utf-8")
    print(f"Written to {README_PATH}")
