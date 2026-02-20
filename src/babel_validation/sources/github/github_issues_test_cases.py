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


class GitHubIssueTest:
    def __init__(self, github_issue: Issue.Issue, assertion: str, param_sets: list[list[str]] = None):
        self.github_issue = github_issue
        self.assertion = assertion
        if param_sets is None:
            param_sets = []
        self.param_sets = param_sets
        if not isinstance(self.param_sets, list):
            raise ValueError(f"param_sets must be a list when creating a GitHubIssueTest({self.github_issue}, {self.assertion}, {self.param_sets})")

        # Derive repo_id from html_url (e.g. https://github.com/org/repo/issues/1 → "org/repo")
        # to avoid slow lazy API calls via github_issue.repository.organization.name.
        parts = github_issue.html_url.split('/')
        self.repo_id = f"{parts[3]}/{parts[4]}"

        self.logger = logging.getLogger(str(self))
        self.logger.info(f"Creating GitHubIssueTest for {github_issue.html_url} {assertion}({param_sets})")

    def __str__(self):
        return f"{self.repo_id}#{self.github_issue.number}: {self.assertion}({len(self.param_sets)} param sets: {json.dumps(self.param_sets)})"

    def test_with_nodenorm(self, nodenorm: CachedNodeNorm) -> Iterator[TestResult]:
        handler = ASSERTION_HANDLERS.get(self.assertion.lower())
        if handler is None:
            raise ValueError(f"Unknown assertion type for {self}: {self.assertion}")
        return handler.test_with_nodenorm(self.param_sets, nodenorm, label=str(self))

    def test_with_nameres(self, nodenorm: CachedNodeNorm, nameres: CachedNameRes, pass_if_found_in_top=5) -> Iterator[TestResult]:
        handler = ASSERTION_HANDLERS.get(self.assertion.lower())
        if handler is None:
            raise ValueError(f"Unknown assertion type: {self.assertion}")
        return handler.test_with_nameres(self.param_sets, nodenorm, nameres, pass_if_found_in_top, label=str(self))


class GitHubIssuesTestCases:
    """
    The idea here is to allow test cases to be efficiently embedded within GitHub issues, to test them
    regularly, and to provide a list of cases where either:
    - An open issue has test cases that are now passing (and so should be updated or maybe even closed).
    - A closed issue has test cases that are now failing (and so should be reopened).
    """

    def __init__(self, github_token: str, github_repositories=None):
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
        self.logger.info("Set up GitHub object ({self.github})")

        if github_repositories is None:
            github_repositories = [
                'NCATSTranslator/Babel',                # https://github.com/NCATSTranslator/Babel
                'NCATSTranslator/NodeNormalization',    # https://github.com/NCATSTranslator/NodeNormalization
                'NCATSTranslator/NameResolution',       # https://github.com/NCATSTranslator/NameResolution
                'TranslatorSRI/babel-validation',       # https://github.com/TranslatorSRI/babel-validation
            ]
        self.github_repositories = github_repositories

        # Prepare regular expressions.
        self.babeltest_pattern = re.compile(r'{{BabelTest\|.*?}}')
        self.babeltest_yaml_pattern = re.compile(r'```yaml\s+babel_tests:\s+.*?\s+```', re.DOTALL)

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

        parts = github_issue.html_url.split('/')
        github_issue_id = f"{parts[3]}/{parts[4]}#{github_issue.number}"
        self.logger.debug(f"Looking for tests in issue {github_issue_id}: {github_issue.title} ({str(github_issue.state)}, {github_issue.html_url})")

        # Is there an issue body at all?
        if not github_issue.body or github_issue.body.strip() == '':
            return []

        # Look for BabelTest syntax.
        testrows = []

        babeltest_matches = re.findall(self.babeltest_pattern, github_issue.body)
        if babeltest_matches:
            for match in babeltest_matches:
                self.logger.info(f"Found BabelTest in issue {github_issue_id}: {match}")

                # Figure out parameters.
                test_string = match
                if test_string.startswith("{{BabelTest|"):
                    test_string = test_string[12:]
                if test_string.endswith("}}"):
                    test_string = test_string[:-2]
                params = test_string.split("|")
                if len(params) < 2:
                    raise ValueError(f"Too few parameters found in BabelTest in issue {github_issue_id}: {match}")
                else:
                    testrows.append(GitHubIssueTest(github_issue, params[0], [params[1:]]))

        babeltest_yaml_matches = re.findall(self.babeltest_yaml_pattern, github_issue.body)
        if babeltest_yaml_matches:
            for match in babeltest_yaml_matches:
                self.logger.info(f"Found BabelTest YAML in issue {github_issue_id}: {match}")

                # Parse string as YAML.
                if match.startswith("```yaml"):
                    match = match[7:]
                if match.endswith("```"):
                    match = match[:-3]
                yaml_dict = yaml.safe_load(match)

                for assertion, original_param_sets in yaml_dict['babel_tests'].items():
                    param_sets = []
                    for param_set in original_param_sets:
                        if isinstance(param_set, str):
                            param_sets.append([param_set])
                        elif isinstance(param_set, list):
                            param_sets.append(param_set)
                        else:
                            raise RuntimeError(f"Unknown parameter set type {param_set} in issue {github_issue_id}")
                    testrows.append(GitHubIssueTest(github_issue, assertion, param_sets))

        return testrows

    def get_all_issues(self, github_repositories = None) -> Iterator[Issue.Issue]:
        """
        Get a list of test rows from one or more repositories.

        :param github_repositories: A list of GitHub repositories to search for test cases. If none is provided,
            we default to the list specified when creating this GitHubIssuesTestCases class.
        :return: A list of TestRows to process.
        """
        if github_repositories is None:
            github_repositories = self.github_repositories

        for repo_id in github_repositories:
            self.logger.info(f"Looking up issues in GitHub repository {repo_id}")
            repo = self.github.get_repo(repo_id, lazy=True)

            issue_count = 0
            for issue in tqdm(repo.get_issues(state='all', sort='updated'), desc=f"Processing issues in {repo_id}"):
                issue_count += 1
                yield issue

            self.logger.info(f"Found {issue_count} issues in GitHub repository {repo_id}")
