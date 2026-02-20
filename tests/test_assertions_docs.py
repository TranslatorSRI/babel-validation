from src.babel_validation.assertions.gen_docs import generate_readme, README_PATH


def test_assertions_readme_is_up_to_date():
    expected = generate_readme()
    actual = README_PATH.read_text(encoding="utf-8")
    assert actual == expected, (
        "assertions/README.md is out of date.\n"
        "Regenerate it with:\n"
        "    uv run python -m src.babel_validation.assertions.gen_docs"
    )
