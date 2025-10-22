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

To run these tests, you need to set up a Python environment:

```shell
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
```

The file [`tests/targets.ini`](./tests/targets.ini) allows you to control which NodeNorm
instance is tested. The `[DEFAULT]` section applies defaults for all the environments.
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
