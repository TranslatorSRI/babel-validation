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

import logging
import re
from typing import Iterator

import yaml

from github import Github, Auth, Issue

from src.babel_validation.assertions import ASSERTION_HANDLERS
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm

_logger = logging.getLogger(__name__)


# Issue bodies are untrusted input: anyone with a GitHub account can write one, and nothing
# reviews them before we parse them and turn them into live API calls. These caps bound what a
# single issue can cost us. They all sit far above anything a real issue contains — an issue
# that trips one is meant to be split up, so exceeding them fails loudly rather than truncating.
MAX_ISSUE_BODY_CHARS = 65536      # GitHub's own issue-body limit; longer means something is wrong
MAX_BABELTESTS_PER_ISSUE = 100    # an issue with more assertions than this is not human-reviewable
MAX_PARAM_SETS_PER_ISSUE = 1000   # bounds the fan-out even when the param_sets are empty
MAX_PARAMS_PER_ISSUE = 1000       # prepare_params_lists fans a whole assertion into ONE POST body

# Assertion names are looked up in ASSERTION_HANDLERS, but the raw name reaches a log line and
# str(self) first, so its shape is checked before it gets that far. Every real NAME matches.
_ASSERTION_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,63}$')


class _NoAliasSafeLoader(yaml.SafeLoader):
    """SafeLoader that refuses YAML anchors, aliases and duplicate keys.

    safe_load blocks code execution but still resolves aliases, and PyYAML shares the aliased
    nodes rather than copying them — so the load itself looks cheap and the cost is paid later,
    by whatever stringifies the result. A 337-byte body of chained anchors expands to a 25 MB
    string the moment anything formats it — an error message's {element!r}, a log line — and a
    couple more levels makes that gigabytes. Nothing in the BabelTest syntax needs an alias, so
    the cheapest fix is to refuse them outright. That covers merge keys (`<<: *x`) too.
    """

    def compose_node(self, parent, index):
        if self.check_event(yaml.events.AliasEvent):
            raise yaml.YAMLError("YAML anchors/aliases are not allowed in a babel_tests block")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        """Reject duplicate keys instead of silently keeping the last one.

        YAML says last-wins, which quietly breaks the assumption this whole feature rests on —
        that a human reading the issue body can see what the run will do. A reviewer reads the
        first `Resolves:` block; the run executes the second.
        """
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.YAMLError(f"duplicate key {key!r} in a babel_tests block")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def issue_id(issue: Issue.Issue) -> str:
    """The human-readable "org/repo#N" identifier for an issue.

    Parsed out of html_url rather than read from issue.repository.full_name:
    search results carry no repository, so that attribute costs two extra REST
    calls (a full issue GET, then a repo GET) for every issue we look at.
    """
    org, repo = issue.html_url.split("/")[3:5]
    return f"{org}/{repo}#{issue.number}"


def _to_list(value, context: str) -> list:
    """Normalize a YAML value that may be a bare string or a list; raise on anything else."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    raise ValueError(f"{context}: expected str or list, got {type(value).__name__}")


def _to_str_list(value, context: str) -> list[str]:
    """_to_list, but every element must be a string.

    YAML 1.1 resolves an unquoted `no`, `on` or `1.5` to a bool or a float, so an
    innocent-looking label can arrive as a non-string and blow up much later in
    prepare_params_lists' param.strip(). Reject it here, where we can say why.
    """
    values = _to_list(value, context)
    for element in values:
        if not isinstance(element, str):
            raise ValueError(
                f"{context}: expected a string, got {type(element).__name__}: {element!r} "
                f"— quote it to keep YAML from reinterpreting it"
            )
    return values


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
            raise ValueError(f"param_sets must be a list when creating a GitHubIssueTest({github_issue}, {assertion}, {param_sets!r})")
        # Checked here rather than in either parser branch: this is the one place the wiki and
        # YAML syntaxes both route through, and it runs before the name reaches a log line,
        # str(self), or the "unknown assertion" message in test_github_issues.py. A name that
        # fails this is junk rather than a typo — every real NAME matches.
        if not _ASSERTION_NAME_RE.match(assertion):
            raise ValueError(
                f"Invalid assertion name in issue {github_issue_id}: {assertion!r} — expected letters, "
                f"digits and underscores only, starting with a letter, at most 64 characters"
            )
        self.github_issue = github_issue
        self.assertion = assertion
        self.param_sets = param_sets if param_sets is not None else []
        self.github_issue_id = github_issue_id

        # %r, not %s: these come from an unreviewed issue body, and repr() escapes exactly the
        # characters str.isprintable() rejects — ANSI escapes, C0/C1 controls, bidi overrides —
        # so nothing reaches an operator's terminal unescaped.
        _logger.info("Creating GitHubIssueTest for %s %r(%r)", github_issue.html_url, assertion, param_sets)

    def __str__(self):
        # Deliberately does not dump param_sets: this string is the `label` on every TestResult
        # this assertion produces, so an issue at the param cap would repeat tens of KB per
        # message. The count is what a reader actually needs.
        return f"{self.github_issue_id}: {self.assertion}({len(self.param_sets)} param sets)"

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
    # This pattern used to end `babel_tests:\s+.*?\s+```. Those three nested backtracking
    # quantifiers made matching cubic on a body that opens a babel_tests block and never closes
    # the fence: 6.8s at 4KB, 53s at 8KB, and hours at GitHub's 65536-character limit. Worse, it
    # runs in issue_has_tests() during *collection*, which pytest-timeout does not cover, so one
    # such issue hung the whole run before a single test started.
    #
    # Anchoring on the newline that has to follow `babel_tests:` in a real fenced block removes
    # the ambiguity — `[^\S\n]*` and `\n` are disjoint, as are `\s+` and the literal after it —
    # leaving one lazy `.*?` to scan to the fence. 0.0008s at 65536 characters, and it matches
    # byte-identical text on every real block. It also stops matching a one-line mention like
    # ```` ```yaml babel_tests: ``` ```` written in prose while *discussing* the syntax, which
    # the old pattern picked up and then failed on (TranslatorSRI/babel-validation#100).
    #
    # Keep it group-free: findall() is called with this pattern and would return the group
    # rather than the whole match.
    _BABELTEST_YAML_RE = re.compile(r'```yaml\s+babel_tests:[^\S\n]*\n.*?```', re.DOTALL)

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

        github_issue_id = issue_id(github_issue)
        self.logger.debug("Looking for tests in issue %s: %s (%s, %s)",
                          github_issue_id, github_issue.title, github_issue.state, github_issue.html_url)

        # Is there an issue body at all?
        if not github_issue.body or github_issue.body.strip() == '':
            return []

        if len(github_issue.body) > MAX_ISSUE_BODY_CHARS:
            raise ValueError(
                f"Issue {github_issue_id} has a {len(github_issue.body):,}-character body, over the "
                f"{MAX_ISSUE_BODY_CHARS:,}-character limit. GitHub caps issue bodies below this, so this "
                f"should be unreachable — treat it as a sign the input is not what we think it is."
            )

        # Look for BabelTest syntax.
        testrows = []

        for babeltest_match in self._BABELTEST_RE.finditer(github_issue.body):
            match = babeltest_match.group(0)
            self.logger.info("Found BabelTest in issue %s: %r", github_issue_id, match)

            # Figure out parameters.
            test_string = babeltest_match.group(1)
            params = test_string.split("|")
            assertion = params[0].strip() if params else ""
            if not assertion:
                raise ValueError(f"Missing assertion name in BabelTest in issue {github_issue_id}: {match}")
            # Wiki syntax: params[0] is the assertion name; params[1:] form a single
            # param_set (may be empty for assertions like Needed), so param_sets is a
            # one-element list: [params[1:]].
            testrows.append(GitHubIssueTest(github_issue_id, github_issue, assertion, [params[1:]]))

        babeltest_yaml_matches = re.findall(self._BABELTEST_YAML_RE, github_issue.body)
        if babeltest_yaml_matches:
            for match in babeltest_yaml_matches:
                self.logger.info("Found BabelTest YAML in issue %s: %r", github_issue_id, match)

                # _NoAliasSafeLoader rather than safe_load: safe_load blocks code execution
                # but still expands aliases and honours merge keys.
                try:
                    yaml_dict = yaml.load(match.removeprefix("```yaml").removesuffix("```"),
                                          Loader=_NoAliasSafeLoader)
                except RecursionError as e:
                    # A few KB of nested `[[[[...]]]]` blows the interpreter's stack inside the
                    # loader. Report it as the malformed block it is rather than dumping a
                    # several-thousand-frame traceback.
                    raise ValueError(
                        f"YAML block in issue {github_issue_id} is nested too deeply to parse"
                    ) from e

                babel_tests = yaml_dict.get('babel_tests') if isinstance(yaml_dict, dict) else None
                if babel_tests is None:
                    raise ValueError(
                        f"YAML block in issue {github_issue_id} matched the detection pattern "
                        f"but contains no 'babel_tests' top-level key: {match!r}"
                    )
                if not isinstance(babel_tests, dict):
                    raise ValueError(
                        f"YAML block in issue {github_issue_id}: 'babel_tests' must be a mapping of "
                        f"assertion name to param sets, but got {type(babel_tests).__name__}: {babel_tests!r}"
                    )

                for assertion, original_param_sets in babel_tests.items():
                    # YAML syntax: each entry under an assertion key becomes one param_set.
                    # A bare string becomes a single-element param_set; a list is used as-is.
                    if not isinstance(assertion, str):
                        raise ValueError(
                            f"YAML block in issue {github_issue_id}: assertion name must be a string, "
                            f"but got {type(assertion).__name__}: {assertion!r}"
                        )
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
                        _to_str_list(ps, f"YAML block in issue {github_issue_id}: assertion '{assertion}' param_set")
                        for ps in normalized
                    ]
                    testrows.append(GitHubIssueTest(github_issue_id, github_issue, assertion, param_sets))

        self._check_issue_size(github_issue_id, testrows)
        return testrows

    @staticmethod
    def _check_issue_size(github_issue_id: str, testrows: list[GitHubIssueTest]) -> None:
        """Reject an issue that would fan out into an unreasonable amount of work.

        Counted across both syntaxes together and once, rather than per block: what costs us is
        the total an issue produces, and a single test item runs all of it. Exceeding a cap
        raises, so the issue's test errors rather than silently running a truncated subset — the
        fix is to split the assertions across several issues.
        """
        if len(testrows) > MAX_BABELTESTS_PER_ISSUE:
            raise ValueError(
                f"Issue {github_issue_id} contains {len(testrows):,} BabelTest assertions, over the "
                f"limit of {MAX_BABELTESTS_PER_ISSUE:,}. Split them across several issues."
            )
        param_set_count = sum(len(t.param_sets) for t in testrows)
        if param_set_count > MAX_PARAM_SETS_PER_ISSUE:
            raise ValueError(
                f"Issue {github_issue_id} contains {param_set_count:,} param sets, over the limit of "
                f"{MAX_PARAM_SETS_PER_ISSUE:,}. Split them across several issues."
            )
        param_count = sum(len(ps) for t in testrows for ps in t.param_sets)
        if param_count > MAX_PARAMS_PER_ISSUE:
            raise ValueError(
                f"Issue {github_issue_id} contains {param_count:,} parameters, over the limit of "
                f"{MAX_PARAMS_PER_ISSUE:,}. Split them across several issues."
            )

    def issue_has_tests(self, issue: Issue.Issue) -> bool:
        """Quick regex check to see if an issue body contains any BabelTest syntax."""
        if not issue.body or issue.body.strip() == '':
            return False
        if len(issue.body) > MAX_ISSUE_BODY_CHARS:
            # Claim it rather than raising: this runs during collection over every issue the
            # search returned, so raising here would abort the whole run for one bad issue.
            # Saying yes routes it to get_test_issues_from_issue(), where it fails on its own.
            return True
        return bool(self._BABELTEST_RE.search(issue.body) or
                    self._BABELTEST_YAML_RE.search(issue.body))

    def get_issues_by_ids(self, issue_ids: list[str]) -> list[Issue.Issue]:
        """
        Fetch specific GitHub issues by their ID strings, supporting three formats:
        - 'org/repo#N'  → direct fetch from that repo, which must be a configured one
        - 'repo#N'      → search self.github_repositories for matching repo name
        - 'N'           → fetch #N from all configured repositories

        Every format resolves only within self.github_repositories. 'org/repo#N' used to be
        fetched from anywhere on GitHub, which made this the weak point of the whole feature:
        assertions are executed from whatever issue body comes back, so any caller able to
        choose an ID could point the run at a repository it controls. Two callers can: --issue,
        and the ID list reloaded from the shared-temp-directory cache in
        tests/github_issues/conftest.py, which is world-writable on a CI runner. Checking
        membership here rather than where --issue is parsed covers both.

        The check also has to come before get_repo(), not after: the 'org/repo#N' pattern's repo
        group is [^#]+, which admits slashes and dots, so an unchecked
        'org/repo/../../elsewhere#1' would reach the GitHub API as a URL path.
        """
        from github import UnknownObjectException
        issues = []
        configured = {r.lower() for r in self.github_repositories}
        for raw_id in issue_ids:
            found = False
            if m := re.match(r'^([^/]+)/([^#]+)#(\d+)$', raw_id):
                # org/repo#N
                full_repo = f"{m.group(1)}/{m.group(2)}"
                if full_repo.lower() in configured:
                    try:
                        issues.append(self.github.get_repo(full_repo).get_issue(int(m.group(3))))
                        found = True
                    except UnknownObjectException:
                        pass
            elif m := re.match(r'^([^/#]+)#(\d+)$', raw_id):
                # repo#N — find repo in configured list
                repo_name, num = m.group(1), int(m.group(2))
                for full_repo in self.github_repositories:
                    parts = full_repo.split('/')
                    if len(parts) >= 2 and parts[1] == repo_name:
                        try:
                            issues.append(self.github.get_repo(full_repo).get_issue(num))
                            found = True
                        except UnknownObjectException:
                            pass
                        break
            elif m := re.match(r'^(\d+)$', raw_id):
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
                    f"Could not resolve issue ID {raw_id!r} in configured repositories "
                    f"{self.github_repositories}. Use 'org/repo#N', 'repo#N', or 'N'."
                )
        return issues

    def get_issues_with_tests(self, github_repositories=None) -> Iterator[Issue.Issue]:
        """Use GitHub search API to find only issues containing BabelTest syntax.

        This is much faster than paginating every issue and filtering with
        issue_has_tests(), because
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
