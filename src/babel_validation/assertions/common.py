from typing import Iterator

from src.babel_validation.assertions import AssertionHandler, ParamsList
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nameres import NameResService
from src.babel_validation.services.nodenorm import NodeNormService


class NeededHandler(AssertionHandler):
    """Placeholder assertion indicating that a test still needs to be written for this issue."""
    NAME = "needed"
    DESCRIPTION = "Marks an issue as needing a test — always fails as a reminder to add real assertions."
    PARAMETERS = ""
    WIKI_EXAMPLES = ["{{BabelTest|Needed}}"]
    YAML_PARAMS = "    - placeholder"

    # Applies to both services, and ignores its params entirely: the assertion
    # records that a test is missing, so there is nothing to evaluate.
    def test_with_nodenorm(self, params_lists: list[ParamsList],
                           nodenorm: NodeNormService,
                           label: str = "") -> Iterator[TestResult]:
        yield self.failed("Test needed for issue")

    def test_with_nameres(self, params_lists: list[ParamsList],
                          nodenorm: NodeNormService, nameres: NameResService,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        yield self.failed("Test needed for issue")
