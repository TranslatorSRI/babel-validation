from src.babel_validation.assertions import AssertionHandler
from src.babel_validation.core.testrow import TestResult, TestStatus


class NeededHandler(AssertionHandler):
    """Placeholder assertion indicating that a test still needs to be written for this issue."""
    NAME = "needed"
    DESCRIPTION = "Marks an issue as needing a test — always fails as a reminder to add real assertions."

    def test_with_nodenorm(self, param_sets, nodenorm, label=""):
        return [TestResult(status=TestStatus.Failed, message=f"Test needed for issue")]

    def test_with_nameres(self, param_sets, nodenorm, nameres, pass_if_found_in_top=5, label=""):
        return [TestResult(status=TestStatus.Failed, message=f"Test needed for issue")]
