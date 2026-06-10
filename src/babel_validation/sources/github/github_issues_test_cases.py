"""
Parse and evaluate BabelTest assertions embedded in GitHub issue bodies.

Terminology
-----------
assertion   — The name of the test type, e.g. "Resolves" or "ResolvesWith".
              Case-insensitive. Maps to a key in ASSERTION_HANDLERS.

param_set   — One set of parameters for a single invocation of an assertion.
              Represented as a list of strings. Each Wiki-syntax line produces
              exactly one param_set; each entry under a YAML assertion key
              produces one param_set.

              Often the first element is "special" (e.g. an expected label or
              Biolink type) and the remaining elements are CURIEs to test,
              but the interpretation is assertion-specific.
              Example: ["CHEBI:15365", "PUBCHEM.COMPOUND:1"]

param_sets  — The full list of param_sets for one assertion in one issue.
              A list of lists (list[list[str]]). YAML syntax allows many
              param_sets for one assertion type in a single block.
              Example: [["CHEBI:15365", "PUBCHEM.COMPOUND:1"],
                        ["MONDO:0005015", "DOID:9351"]]
"""

import json
import logging
import re
from typing import Iterator

import yaml

from github import Github, Auth, Issue
from tqdm import tqdm

from src.babel_validation.assertions import ASSERTION_HANDLERS
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm

_logger = logging.getLogger(__name__)


def _to_list(value, context: str) -> list:
    """Normalize a YAML value that may be a bare string or a list; raise on anything else."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    raise ValueError(f"{context}: expected str or list, got {type(value).__name__}")


class GitHubIssueTest:
    """Represents one assertion extracted from a GitHub issue body — an assertion name paired with a list of param_sets to evaluate."""

    def __init__(self, github_issue_id: str, github_issue: Issue.Issue, assertion: str, param_sets: list[list[str]] = None):
        """
        :param github_issue_id: Human-readable issue identifier, e.g. "org/repo#42".
        :param github_issue: The PyGitHub Issue object this test was extracted from.
        :param assertion: The assertion name (case-insensitive), e.g. "Resolves" or "HasLabel".
                          Must match a key in ASSERTION_HANDLERS.
        :param param_sets: A list of param_sets (list[list[str]]) to evaluate for this assertion.
                           Each inner list is one param_set — see module docstring for details.
        """
        if not isinstance(param_sets, list) and param_sets is not None:
            raise ValueError(f"param_sets must be a list when creating a GitHubIssueTest({github_issue}, {assertion}, {param_sets})")
        self.github_issue = github_issue
        self.assertion = assertion
        self.param_sets = param_sets if param_sets is not None else []
        self.github_issue_id = github_issue_id

        _logger.info("Creating GitHubIssueTest for %s %s(%s)", github_issue.html_url, assertion, param_sets)

    def __str__(self):
        return f"{self.github_issue_id}: {self.assertion}({len(self.param_sets)} param sets: {json.dumps(self.param_sets)})"

    def _get_handler(self):
        handler = ASSERTION_HANDLERS.get(self.assertion.lower())
        if handler is None:
            raise ValueError(f"Unknown assertion type for {self}: {self.assertion}")
        return handler

    def test_with_nodenorm(self, nodenorm: CachedNodeNorm) -> Iterator[TestResult]:
        return self._get_handler().test_with_nodenorm(self.param_sets, nodenorm, label=str(self))

    def test_with_nameres(self, nodenorm: CachedNodeNorm, nameres: CachedNameRes, pass_if_found_in_top=5) -> Iterator[TestResult]:
        return self._get_handler().test_with_nameres(self.param_sets, nodenorm, nameres, pass_if_found_in_top, label=str(self))


class GitHubIssuesTestCases:
    """
    The idea here is to allow test cases to be efficiently embedded within GitHub issues, to test them
    regularly, and to provide a list of cases where either:
    - An open issue has test cases that are now passing (and so should be updated or maybe even closed).
    - A closed issue has test cases that are now failing (and so should be reopened).
    """

    # Case-insensitive, matching the case-insensitivity of assertion names.
    # Group 1 captures everything between '{{BabelTest|' and '}}'.
    _BABELTEST_RE = re.compile(r'{{BabelTest\|(.*?)}}', re.IGNORECASE)
    _BABELTEST_YAML_RE = re.compile(r'```yaml\s+babel_tests:\s+.*?\s+```', re.DOTALL)

    def __init__(self, github_token: str, github_repositories):
        """
        Create a GitHubIssuesTestCase object.

        Requires a GitHub authentication token. You can generate a personal authentication token
        at https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#about-personal-access-tokens,
        or you can read the GITHUB_TOKEN during a GitHub Action (https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

        :param github_token: A GitHub authentication to use for making these queries.
        :param github_repositories: A list of GitHub repositories to pull issues from, specified as 'organization/repo'.
        """
        self.github_token = github_token
        if not self.github_token or self.github_token.strip() == '':
            raise ValueError("No GitHub authentication token provided.")

        self.github = Github(auth=Auth.Token(self.github_token))
        self.logger = logging.getLogger(self.__class__.__name__)

        if not github_repositories:
            raise ValueError("No GitHub repositories specified in `github_repositories`.")
        self.github_repositories = github_repositories
        self.logger.info("Configured GitHub repositories: %s", self.github_repositories)

    def get_test_issues_from_issue(self, github_issue: Issue.Issue) -> list[GitHubIssueTest]:
        """
        Extract test rows from a single GitHub issue.

        Two syntaxes are supported:
        - Wiki syntax: {{BabelTest|AssertionType|param1|param2|...}}
        - YAML syntax:

        ```yaml
        babel_tests:
            assertion:
            - param1
            - ['param1', 'param2']
        ```

        For the full list of supported assertion types and their parameters, see
        src/babel_validation/assertions/README.md or inspect ASSERTION_HANDLERS.keys().

        :param github_issue: A single GitHub issue to extract test cases from.
        :return: A list of GitHubIssueTest objects found in the issue body.
        """

        github_issue_id = f"{github_issue.repository.full_name}#{github_issue.number}"
        self.logger.debug("Looking for tests in issue %s: %s (%s, %s)",
                          github_issue_id, github_issue.title, github_issue.state, github_issue.html_url)

        # Is there an issue body at all?
        if not github_issue.body or github_issue.body.strip() == '':
            return []

        # Look for BabelTest syntax.
        testrows = []

        for babeltest_match in self._BABELTEST_RE.finditer(github_issue.body):
            match = babeltest_match.group(0)
            self.logger.info("Found BabelTest in issue %s: %s", github_issue_id, match)

            # Figure out parameters.
            test_string = babeltest_match.group(1)
            params = test_string.split("|")
            if not params or not params[0]:
                raise ValueError(f"Missing assertion name in BabelTest in issue {github_issue_id}: {match}")
            # Wiki syntax: params[0] is the assertion name; params[1:] form a single
            # param_set (may be empty for assertions like Needed), so param_sets is a
            # one-element list: [params[1:]].
            testrows.append(GitHubIssueTest(github_issue_id, github_issue, params[0], [params[1:]]))

        babeltest_yaml_matches = re.findall(self._BABELTEST_YAML_RE, github_issue.body)
        if babeltest_yaml_matches:
            for match in babeltest_yaml_matches:
                self.logger.info("Found BabelTest YAML in issue %s: %s", github_issue_id, match)

                # Parse string as YAML.
                yaml_dict = yaml.safe_load(match.removeprefix("```yaml").removesuffix("```"))

                babel_tests = yaml_dict.get('babel_tests') if isinstance(yaml_dict, dict) else None
                if babel_tests is None:
                    raise ValueError(
                        f"YAML block in issue {github_issue_id} matched the detection pattern "
                        f"but contains no 'babel_tests' top-level key: {match!r}"
                    )

                for assertion, original_param_sets in babel_tests.items():
                    # YAML syntax: each entry under an assertion key becomes one param_set.
                    # A bare string becomes a single-element param_set; a list is used as-is.
                    if original_param_sets is None:
                        raise ValueError(
                            f"YAML block in issue {github_issue_id}: assertion '{assertion}' has a null "
                            f"param list — use an empty list [] or remove the entry"
                        )
                    normalized = _to_list(
                        original_param_sets,
                        f"YAML block in issue {github_issue_id}: assertion '{assertion}'"
                    )
                    param_sets = [
                        _to_list(ps, f"YAML block in issue {github_issue_id}: assertion '{assertion}' param_set")
                        for ps in normalized
                    ]
                    testrows.append(GitHubIssueTest(github_issue_id, github_issue, assertion, param_sets))

        return testrows

    def issue_has_tests(self, issue: Issue.Issue) -> bool:
        """Quick regex check to see if an issue body contains any BabelTest syntax."""
        if not issue.body or issue.body.strip() == '':
            return False
        return bool(self._BABELTEST_RE.search(issue.body) or
                    self._BABELTEST_YAML_RE.search(issue.body))

    def get_issues_by_ids(self, issue_ids: list[str]) -> list[Issue.Issue]:
        """
        Fetch specific GitHub issues by their ID strings, supporting three formats:
        - 'org/repo#N'  → direct fetch from that repo
        - 'repo#N'      → search self.github_repositories for matching repo name
        - 'N'           → fetch #N from all configured repositories
        """
        from github import UnknownObjectException
        issues = []
        for issue_id in issue_ids:
            found = False
            if m := re.match(r'^([^/]+)/([^#]+)#(\d+)$', issue_id):
                # org/repo#N
                issue = self.github.get_repo(f"{m.group(1)}/{m.group(2)}").get_issue(int(m.group(3)))
                issues.append(issue)
                found = True
            elif m := re.match(r'^([^/#]+)#(\d+)$', issue_id):
                # repo#N — find repo in configured list
                repo_name, num = m.group(1), int(m.group(2))
                for full_repo in self.github_repositories:
                    parts = full_repo.split('/')
                    if len(parts) >= 2 and parts[1] == repo_name:
                        issues.append(self.github.get_repo(full_repo).get_issue(num))
                        found = True
                        break
            elif m := re.match(r'^(\d+)$', issue_id):
                # N — try all configured repos; skip repos that don't have this issue number.
                num = int(m.group(1))
                for full_repo in self.github_repositories:
                    try:
                        issues.append(self.github.get_repo(full_repo).get_issue(num))
                        found = True
                    except UnknownObjectException:
                        pass
            if not found:
                raise ValueError(
                    f"Could not resolve issue ID {issue_id!r} in configured repositories "
                    f"{self.github_repositories}. Use 'org/repo#N', 'repo#N', or 'N'."
                )
        return issues

    def get_issues_with_tests(self, github_repositories=None) -> Iterator[Issue.Issue]:
        """Use GitHub search API to find only issues containing BabelTest syntax.

        This is much faster than get_all_issues() + issue_has_tests() filtering because
        it only fetches issues that match the search query rather than paginating through
        every issue in each repository.

        Note: GitHub's search index has a ~60-second lag for very recent edits. For
        immediate testing of freshly-edited issues, use --issue which calls
        get_issues_by_ids() directly.
        """
        if github_repositories is None:
            github_repositories = self.github_repositories
        for repo_id in github_repositories:
            seen_numbers = set()
            for keyword in ['{{BabelTest', 'babel_tests:']:
                query = f'"{keyword}" is:issue in:body repo:{repo_id}'
                self.logger.info("Searching GitHub issues with query: %s", query)
                for issue in self.github.search_issues(query):
                    if issue.number not in seen_numbers:
                        seen_numbers.add(issue.number)
                        if self.issue_has_tests(issue):
                            yield issue

    def get_all_issues(self, github_repositories=None) -> Iterator[Issue.Issue]:
        """
        Get a list of test rows from one or more repositories.

        :param github_repositories: A list of GitHub repositories to search for test cases. If none is provided,
            we default to the list specified when creating this GitHubIssuesTestCases class.
        :return: A list of TestRows to process.
        """
        if github_repositories is None:
            github_repositories = self.github_repositories

        for repo_id in github_repositories:
            self.logger.info("Looking up issues in GitHub repository %s", repo_id)
            repo = self.github.get_repo(repo_id, lazy=True)

            issue_count = 0
            for issue in tqdm(repo.get_issues(state='all', sort='updated'), desc=f"Processing issues in {repo_id}"):
                issue_count += 1
                yield issue

            self.logger.info("Found %d issues in GitHub repository %s", issue_count, repo_id)
