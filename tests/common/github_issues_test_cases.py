import json
import logging
import re
import time
from typing import Iterator

import requests
import yaml

from tests.common.testrow import TestRow, TestResult, TestStatus
from github import Github, Auth, Issue
from tqdm import tqdm

class CachedNodeNorm:
    def __init__(self, nodenorm_url: str):
        self.nodenorm_url = nodenorm_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNodeNorm({self.nodenorm_url})"

    def normalize_curies(self, curies: list[str], **params) -> str:
        time_started = time.time_ns()
        curies_set = set(curies)
        cached_curies = curies_set & self.cache.keys()
        curies_to_be_queried = curies_set - cached_curies

        # Make query.
        params['curies'] = list(curies_to_be_queried)

        response = requests.post(self.nodenorm_url + "get_normalized_nodes", json=params)
        response.raise_for_status()
        result = response.json()

        for curie in cached_curies:
            result[curie] = self.cache[curie]

        for curie in curies_to_be_queried:
            self.cache[curie] = result.get(curie, None)

        time_taken_sec = (time.time_ns() - time_started) / 1E9
        self.logger.info(f"Normalizing {len(curies_to_be_queried)} CURIEs {curies_to_be_queried} (with {len(cached_curies)} CURIEs cached) with params {params} on {self} in {time_taken_sec:.3f}s")

        return result

    def normalize_curie(self, curie, **params):
        if curie in self.cache:
            return self.cache[curie]
        return self.normalize_curies([curie], **params)[curie]


class GitHubIssueTest:
    def __init__(self, github_issue: Issue.Issue, assertion: str, param_sets: list[list[str]] = None):
        self.github_issue = github_issue
        self.assertion = assertion
        if param_sets is None:
            param_sets = []
        self.param_sets = param_sets

        self.logger = logging.getLogger(str(self))
        self.logger.info(f"Creating GitHubIssueTest for {github_issue.html_url} {assertion}({param_sets})")

    def __str__(self):
        return f"{self.github_issue.repository.organization.name}/{self.github_issue.repository.name}#{self.github_issue.number}: {self.assertion}({json.dumps(self.param_sets)})"

    def expect_param_count(self, params: list[str], expected_count: int):
        if len(params) != expected_count:
            raise ValueError(f"Expected {expected_count} parameters for assertion {self.assertion}, but got {len(params)}")

    def test_with_nodenorm(self, nodenorm: CachedNodeNorm) -> Iterator[TestResult]:
        match self.assertion.lower():
            case "resolves":
                curies_to_resolve = [params[0] for params in self.param_sets]
                nodenorm.normalize_curies(curies_to_resolve)

                for params in self.param_sets:
                    self.expect_param_count(params, 1)
                    curie = params[0]

                    # Make sure we can resolve this CURIE.
                    result = nodenorm.normalize_curie(curie)
                    if not result:
                        yield TestResult(status=TestStatus.Failed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
                    else:
                        yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}")

            case "resolveswith":
                curies_to_test = set()
                for params in self.param_sets:
                    curies_to_test.add(params[0])
                    curies_to_test.add(params[1])

                nodenorm.normalize_curies(list(curies_to_test))
                for params in self.param_sets:
                    self.expect_param_count(params, 2)
                    curie, expected_curie = params

                    # Make sure we can resolve this CURIE.
                    result = self.nodenorm.normalize_curie(curie)
                    if not result:
                        yield TestResult(status=TestStatus.Failed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
                    elif result['id']['identifier'] == expected_curie:
                        yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm} as expected")
                    else:
                        yield TestResult(status=TestStatus.Failed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}, but expected {expected_curie}")

            case _:
                raise ValueError(f"Unknown assertion type: {self.assertion}")

    def test_with_nameres(self) -> TestResult:
        match self.assertion.lower():
            case "resolves":
                # Nothing we can do about this with NameRes.
                return TestResult(status=TestStatus.Skipped, message="Cannot test Resolves assertion with Name Resolution service")
            case "resolveswith":
                # Nothing we can do about this with NameRes.
                return TestResult(status=TestStatus.Skipped, message="Cannot test Resolves assertion with Name Resolution service")
            case _:
                raise ValueError(f"Unknown assertion type: {self.assertion}")


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

        This is where we describe our test case recording language. I think we should support two formats:
        - Wiki syntax: {{BabelTest|AssertionType|param1|param2|...}}
        - YAML syntax, which requires a YAML type box that looks like this:

        ```yaml
        babel_tests:
            assertion:
            - param1
            - ['param1', 'param2']
            - {'param1': 'value1', 'param2': 'value2'}
        ```

        We currently support the following assertions:
        - Resolves: Test whether any of the parameters can be resolved.
        - DoesNotResolve: Ensure that the parameters do not resolve.
        - ResolvesWith: Test whether all the parameters resolve together.

        :param github_issue: A single GitHub issue to extract test cases from.
        :return: An iterator over TestRows.
        """

        github_issue_id = f"{github_issue.repository.organization.name}/{github_issue.repository.name}#{github_issue.number}"
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
                elif len(params) == 2:
                    testrows.append(GitHubIssueTest(github_issue, params[0], [params]))
                else:
                    testrows.append(GitHubIssueTest(github_issue, params[0], [params]))

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

                for assertion, param_sets in yaml_dict['babel_tests'].items():
                    testrows.append(GitHubIssueTest(github_issue, assertion, param_sets))

        return testrows

    def get_test_issues(self, github_repositories = None, include_issues_without_tests = False) -> Iterator[GitHubIssueTest]:
        """
        Get a list of test rows from one or more repositories.

        :param github_repositories: A list of GitHub repositories to search for test cases. If none is provided,
            we default to the list specified when creating this GitHubIssuesTestCases class.
        :param include_issues_without_tests: If true, include issues that do not contain any test cases. Default: false.
        :return: A list of TestRows to process.
        """
        if github_repositories is None:
            github_repositories = self.github_repositories

        for repo_id in github_repositories:
            self.logger.info(f"Looking up issues in GitHub repository {repo_id}")
            repo = self.github.get_repo(repo_id)

            issue_count = 0
            for issue in tqdm(repo.get_issues(state='all', sort='updated'), desc=f"Processing issues in {repo_id}"):
                issue_count += 1
                test_issues = self.get_test_issues_from_issue(issue)

                if not include_issues_without_tests and not test_issues:
                    continue

                for test_issue in test_issues:
                    yield test_issue

            self.logger.info(f"Found {issue_count} issues in GitHub repository {repo_id}")
