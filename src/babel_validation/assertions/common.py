from src.babel_validation.assertions import AssertionHandler


class NeededHandler(AssertionHandler):
    """Placeholder assertion indicating that a test still needs to be written for this issue."""
    NAME = "needed"
    DESCRIPTION = "Marks an issue as needing a test — always fails as a reminder to add real assertions."
    PARAMETERS = ""
    WIKI_EXAMPLES = ["{{BabelTest|Needed}}"]
    YAML_PARAMS = "    - placeholder"

    def test_with_nodenorm(self, params_lists, nodenorm, label=""):
        yield self.failed("Test needed for issue")

    def test_with_nameres(self, params_lists, nodenorm, nameres, pass_if_found_in_top=5, label=""):
        yield self.failed("Test needed for issue")
