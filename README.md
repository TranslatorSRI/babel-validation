# Babel Validator

This repository has several tools for validating the outputs from
[Babel](https://github.com/TranslatorSRI/Babel) runs, which are the
underlying data used for the Translator
[Node Normalization](https://nodenorm.transltr.io/docs) and
[Name Resolver](https://name-lookup.transltr.io/docs) services.

## PyTest

The best tests in this repository are Python tests stored in the [`./tests`](./tests/) folder.
This includes both unit tests as well as "Google Sheet"-based tests, which uses
a [shared Google Sheet](https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?gid=0#gid=0) containing facts that we can use to test a NodeNorm instance.

To run these tests, you need to [install `uv`](https://docs.astral.sh/uv/getting-started/installation/).
You can then use `uv` to run the tests. The file [`tests/targets.ini`](./tests/targets.ini) allows you to
control which NodeNorm instance is tested. The `[DEFAULT]` section applies defaults for all the environments.
For example, to run all the tests on the `dev` instance, you can use `--target`:

```shell
$ pytest --target dev
============================= test session starts ==============================
platform darwin -- Python 3.13.3, pytest-8.3.3, pluggy-1.5.0
testing target 'dev': {'nodenormurl': 'https://nodenormalization-sri.renci.org/', 'nameresurl': 'https://name-resolution-sri.renci.org/', 'namereslimit': '20', 'nameresxfailifintop': '5'}
included categories: set()
excluded categories: set()
rootdir: /Users/gaurav/Developer/translator/babel-validation
collected 4338 items 
[...]
```

Google Tests have a `Category` column. To filter based on this column, you can
specify a `--category` on the command line.

```shell
$ pytest --target dev --category "Unit Tests" tests/nodenorm/test_nodenorm_from_gsheet.py
==================================================================== test session starts ====================================================================
platform darwin -- Python 3.13.3, pytest-8.3.3, pluggy-1.5.0
testing target 'dev': {'nodenormurl': 'https://nodenormalization-sri.renci.org/', 'nameresurl': 'https://name-resolution-sri.renci.org/', 'namereslimit': '20', 'nameresxfailifintop': '5'}
included categories: {'Unit Tests'}
excluded categories: set()
rootdir: /Users/gaurav/Developer/translator/babel-validation/tests
configfile: pytest.ini
collected 2010 items                                                                                                                                        

tests/nodenorm/test_nodenorm_from_gsheet.py sssssxsssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss.ss.x.....sssssssssssssssssssss.ssssss [  5%]
ssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss...........ssss.....ss.........s...x..sxsssssssssss.ssssss..sssssssssssssssssss [ 12%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 20%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 27%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 34%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 42%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 49%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 57%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 64%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 71%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 79%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 86%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss [ 94%]
sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss                                 [100%]

======================================================= 41 passed, 1965 skipped, 4 xfailed in 10.11s ========================================================
```

### GitHub issue tests

Assertions can also be embedded directly in GitHub issue bodies — see
[`src/babel_validation/assertions/README.md`](./src/babel_validation/assertions/README.md)
for the syntax and the available assertion types. The repositories scanned for them are
listed under `Repositories` in the `[DEFAULT]` section of
[`tests/targets.ini`](./tests/targets.ini).

Issue bodies are untrusted input, so the harness caps what one issue may contain — 100
assertions, 1,000 params lists, 1,000 parameters, 1,000 characters per parameter — and
rejects YAML anchors, aliases and duplicate keys. An issue over a cap fails loudly rather
than running part of itself; split it into several issues. The caps are listed in
[`src/babel_validation/assertions/README.md`](./src/babel_validation/assertions/README.md).
`--issue` resolves only within the configured `Repositories`, so a run can never be pointed
at assertions from somewhere else.

Beware when *discussing* the syntax in an issue: a complete `{{BabelTest|...}}` marker is
picked up wherever it appears, backticks included, and an unrecognised assertion name fails
the run rather than being ignored. Quote a partial marker instead — the pattern needs the
closing `}}` to match.

```shell
$ pytest tests/github_issues --target dev                       # every issue carrying assertions
$ pytest tests/github_issues --target dev --issue 'org/repo#42' # just one (also 'repo#42' or '42')
```

These tests need a `GITHUB_TOKEN`, in the environment or in a `.env` file. Without one they
**skip rather than fail**, so a run can look green having tested nothing. Generate a
[personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens);
inside a GitHub Action, use the
[automatic `GITHUB_TOKEN`](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
instead.

The token is not needed for authentication as such — every repository we scan is public, and
both the single-issue and search endpoints answer unauthenticated requests. It is needed for
the [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api):

| | Unauthenticated | With a token |
| --- | --- | --- |
| Core | 60 / hour, **per IP** | 5,000 / hour |
| [Search](https://docs.github.com/en/rest/search/search) | 10 / minute | 30 / minute |

Discovery is search-bound, not core-bound: two searches per configured repository (one per
trigger keyword, plus a request per extra page of results), and then no core request at all,
because a search result already carries the issue `body` and `html_url` the harness needs.
Scanning the five configured repositories currently finds 96 issues for zero core requests.

Core requests are spent re-hydrating issues one at a time, which happens whenever the cached
ID list is reused instead of the search being repeated — notably in every `pytest-xdist`
worker after the first. That path costs one request per issue per worker, so an
unauthenticated run would exhaust the 60/hour core budget well before finishing.

`GET /rate_limit` reports what is left without itself counting against the limit
([docs](https://docs.github.com/en/rest/rate-limit/rate-limit)). Note that the search window
resets every 60 seconds, so its counter is often back at zero by the time you look:

```shell
$ curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit
```

## Log Analysis

The Jupyter Notebook in `log-analysis/` contains some basic analysis of the
logs from NodeNorm (and, someday, NameRes) instances.

## The Babel Validator Vue Application

The easiest way to validate Babel results on NodeNorm is by running the
Vue app.

```shell
$ cd website-vue3-vite
$ npm install
$ npm run dev
```

This will start a local web application and report the URL for accessing it. This website
retrieves tests from [a Google Sheet document](https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?usp=sharing)
and displays their results across multiple NodeNorm (and, someday, NameRes) endpoints.

A new website is in development at `website/` and is currently deployed to https://translatorsri.github.io/babel-validation/.

## The Babel Validator in Scala

An initial version of the Babel Validator was written in Scala, but this is no longer being maintained.
It is available in the `scala-validation/` directory.

### Subcommands supported by Babel Validator

The main Babel Validator 

### diff

```shell
$ sbt diff {latest Babel output} {earlier Babel output} --n-cores {number of cores} --output {output directory for Diff files}
```

Generates a list of differences between two versions of Babel outputs.
