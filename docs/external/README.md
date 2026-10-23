# Bringing test cases in from outside

**Status: proposal, not a decision.** These notes ask where test cases contributed by other
teams should live, and how someone with a lot of them — a data file to normalize, or a curated
list of things Babel gets wrong — brings them in at once. Read them to argue with them: this
directory is meant to be revised, or left here as the record of why we went one way.

The BabelTest issue syntax (`src/babel_validation/assertions/README.md`) is right for one or
ten cases and wrong for a thousand: an issue is capped at 100 assertions and 1,000 parameters,
and a thousand-row issue is unreadable anyway. #149 replaces the Babel Validation Google Sheet
with a YAML file in this repository, which settles where *our* rows live. It does not settle
the outside case.

## Two questions, not two options

The two designs this started from — contributors keep test files in their own GitHub repos
which we link to, or a RENCI-hosted app with a database where people upload data, normalize
it and flag errors — answer different questions:

1. **Where do bulk test cases live?** The source of truth the nightly run reads.
2. **How does someone with raw data turn it into test cases?** The tooling in front of that.

A workspace app answers the second. Its output is still a set of expectations that need a
home, so it is not an alternative to the first; if we build it, it is a front-end that exports
to wherever the first question decides. As a source of truth a database is the weakest choice.
So most of these notes are about the first question, and the second becomes a later, smaller
decision.

## Recommendation, in one paragraph

Git files as the source of truth, staged behind #149: a records loader that can read more than
one source; `sources/<team>/` directories in this repo with `CODEOWNERS` as the ordinary
contribution path; a SHA-pinned submodule plus an adapter for a source that owns its own repo
and format (the Translator `NCATSTranslator/Tests` repo is the first, and it is public); and a
static client-side page in `website/` as the cheap workspace, before anyone pays for a hosted
one. The reasoning, the challenges and the alternatives are in the files below.

## Contents

| File | What it covers |
|---|---|
| [what-exists.md](what-exists.md) | The threads this builds on, what the sheet can say that issue assertions cannot, and the Translator Tests repo |
| [git-files.md](git-files.md) | Option 1: four mechanisms for git-hosted sources and the challenges they share |
| [workspace.md](workspace.md) | Option 2: a hosted workspace, what it uniquely offers, and the cheap version |
| [alternatives.md](alternatives.md) | Everything else considered, and why not |
| [plan.md](plan.md) | Suggested staging and the open questions |

## Ground rules that apply to all of it

These come from `CLAUDE.md`'s *Untrusted Input* section and are not up for trade:

- A file someone else wrote is untrusted, whatever mechanism delivered it and however it is
  pinned. Every guard the issue loader has applies to any new loader.
- Nothing published — the report, the website, a commit — may contain the Google Sheet's ID or
  a link to either sheet. Sheet *content* is fine to publish; a 1,919-row snapshot is already
  checked in at `tests/data/`.
- Skipping looks like passing. A source that fails to load must fail the run loudly, not
  collect nothing.
