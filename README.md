# Babel Validator

This repository has several tools for validating the outputs from
[Babel](https://github.com/TranslatorSRI/Babel) runs, which are the
underlying data used for the Translator
[Node Normalization](https://nodenorm.transltr.io/1.3/docs) and
[Name Resolver](https://name-lookup.transltr.io/docs) services.

## The Babel Validator Vue Application

The easiest way to validate Babel results on NodeNorm is by running the
Vue app.

```shell
$ cd website
$ npm install
$ npm run dev
```

This will start a local web application and report the URL for accessing it. This website
retrieves tests from [a Google Sheet document](https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?usp=sharing)
and displays their results across multiple NodeNorm (and, someday, NameRes) endpoints.

## Subcommands supported by Babel Validator

The main Babel Validator 

### diff

```shell
$ sbt diff {latest Babel output} {earlier Babel output} --n-cores {number of cores} --output {output directory for Diff files}
```

Generates a list of differences between two versions of Babel outputs.