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

cached_node_norms_by_url = {}

class CachedNodeNorm:
    def __init__(self, nodenorm_url: str):
        self.nodenorm_url = nodenorm_url
        self.logger = logging.getLogger(str(self))
        self.cache = {}

    def __str__(self):
        return f"CachedNodeNorm({self.nodenorm_url})"

    @staticmethod
    def from_url(nodenorm_url: str) -> 'CachedNodeNorm':
        if nodenorm_url not in cached_node_norms_by_url:
            cached_node_norms_by_url[nodenorm_url] = CachedNodeNorm(nodenorm_url)
        return cached_node_norms_by_url[nodenorm_url]

    def normalize_curies(self, curies: list[str], **params) -> dict[str, dict]:
        if not curies:
            raise ValueError(f"curies must not be empty when calling normalize_curies({curies}, {params}) on {self}")
        if not isinstance(curies, list):
            raise ValueError(f"curies must be a list when calling normalize_curies({curies}, {params}) on {self}")

        time_started = time.time_ns()
        curies_set = set(curies)
        cached_curies = curies_set & self.cache.keys()
        curies_to_be_queried = curies_set - cached_curies

        # Make query.
        result = {}
        if curies_to_be_queried:
            params['curies'] = list(curies_to_be_queried)

            self.logger.debug(f"Called NodeNorm {self} with params {params}")
            response = requests.post(self.nodenorm_url + "get_normalized_nodes", json=params)
            response.raise_for_status()
            result = response.json()

            for curie in curies_to_be_queried:
                self.cache[curie] = result.get(curie, None)

        for curie in cached_curies:
            result[curie] = self.cache[curie]

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
        if not isinstance(self.param_sets, list):
            raise ValueError(f"param_sets must be a list when creating a GitHubIssueTest({self.github_issue}, {self.assertion}, {self.param_sets})")

        self.logger = logging.getLogger(str(self))
        self.logger.info(f"Creating GitHubIssueTest for {github_issue.html_url} {assertion}({param_sets})")

    def __str__(self):
        return f"{self.github_issue.repository.organization.name}/{self.github_issue.repository.name}#{self.github_issue.number}: {self.assertion}({len(self.param_sets)} param sets: {json.dumps(self.param_sets)})"

    def test_with_nodenorm(self, nodenorm: CachedNodeNorm) -> Iterator[TestResult]:
        yielded_values = False
        match self.assertion.lower():
            case "resolves":
                if not self.param_sets:
                    return TestResult(status=TestStatus.Failed, message=f"No parameters provided in {self}")

                curies_to_resolve = [param for params in self.param_sets for param in params]
                nodenorm.normalize_curies(curies_to_resolve)

                # Enumerate curies.
                for index, curies in enumerate(self.param_sets):
                    if not curies:
                        return TestResult(status=TestStatus.Failed, message=f"No parameters provided in paramset {index} in {self}")

                    for curie in curies:
                        result = nodenorm.normalize_curie(curie)
                        if not result:
                            yield TestResult(status=TestStatus.Failed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
                            yielded_values = True
                        else:
                            yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}")
                            yielded_values = True

            case "doesnotresolve":
                if not self.param_sets:
                    return TestResult(status=TestStatus.Failed, message=f"No parameters provided in {self}")

                curies_to_resolve = [param for params in self.param_sets for param in params]
                nodenorm.normalize_curies(curies_to_resolve)

                # Enumerate curies.
                for index, curies in enumerate(self.param_sets):
                    if not curies:
                        return TestResult(status=TestStatus.Failed, message=f"No parameters provided in paramset {index} in {self}")

                    for curie in curies:
                        result = nodenorm.normalize_curie(curie)
                        if not result:
                            yield TestResult(status=TestStatus.Passed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm} as expected")
                            yielded_values = True
                        else:
                            yield TestResult(status=TestStatus.Failed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}, but expected not to resolve")
                            yielded_values = True

                if not yielded_values:
                    return TestResult(status=TestStatus.Failed, message=f"No test results returned in {self}")

            case "resolveswith":
                if not self.param_sets:
                    return TestResult(status=TestStatus.Failed, message=f"No parameters provided in {self}")

                curies_to_resolve = [param for params in self.param_sets for param in params]
                nodenorm.normalize_curies(curies_to_resolve)

                for curies in self.param_sets:
                    results = nodenorm.normalize_curies(curies)

                    # Find the first good result.
                    first_good_result = None
                    for curie, result in results.items():
                        if result is not None and first_good_result is None:
                            first_good_result = result
                            break

                    if first_good_result is None:
                        return TestResult(status=TestStatus.Failed, message=f"None of the CURIEs {curies} could be resolved on {nodenorm}")

                    # Check all the results.
                    for curie, result in results.items():
                        if result is None:
                            yield TestResult(status=TestStatus.Failed, message=f"CURIE {curie} could not be resolved, and so is not equal to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)} on {nodenorm}")
                            yielded_values = True
                            continue

                        if json.dumps(first_good_result, sort_keys=True) == json.dumps(result, sort_keys=True):
                            yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)}")
                            yielded_values = True

                        else:
                            yield TestResult(status=TestStatus.Failed, message=f"Resolved {curie} to {json.dumps(result, indent=2, sort_keys=True)}, which is different from the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)} on {nodenorm}")
                            yielded_values = True

                if not yielded_values:
                    return TestResult(status=TestStatus.Failed, message=f"No test results returned in {self}")

            case "resolveswithtype":
                if not self.param_sets:
                    return TestResult(status=TestStatus.Failed, message=f"No parameters provided in {self}")

                for index, params in enumerate(self.param_sets):
                    if len(params) < 2:
                        return TestResult(status=TestStatus.Failed, message=f"Too few parameters provided in param set {index} in {self}: {params}")
                    expected_biolink_type = params[0]
                    curies = params[1:]

                    results = nodenorm.normalize_curies(curies)
                    for curie in curies:
                        biolink_types = results[curie]['type']
                        if expected_biolink_type in biolink_types:
                            yield TestResult(status=TestStatus.Passed, message=f"Biolink types {biolink_types} for CURIE {curie} includes expected Biolink type {expected_biolink_type}")
                            yielded_values = True
                        else:
                            yield TestResult(status=TestStatus.Failed, message=f"Biolink types {biolink_types} for CURIE {curie} does not include expected Biolink type {expected_biolink_type}")
                            yielded_values = True

            # These are NameRes tests, not NodeNorm tests.
            case "searchbyname":
                return

            # This is a special assertion to remind ourselves that we need to add tests here.
            case "needed":
                return TestResult(status=TestStatus.Failed, message=f"Test needed for issue")

            case _:
                raise ValueError(f"Unknown assertion type for {self}: {self.assertion}")

        if not yielded_values:
            return TestResult(status=TestStatus.Failed, message=f"No test results returned in {self}")

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

        github_issue_id = f"{github_issue.number}"
            # Ideally, we would use:
            #   f"{github_issue.repository.organization.name}/{github_issue.repository.name}#{github_issue.number}"
            # But that is very slow.
            # TODO: Wrap Issue.Issue so that we can store orgName and repoName locally so we don't need to call out
            # to figure it out.
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
        :param include_issues_without_tests: If true, include issues that do not contain any test cases. Default: false.
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
