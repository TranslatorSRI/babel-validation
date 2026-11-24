# Option 2: a hosted workspace

Upload a file → batch NodeNorm / NameRes → flag disagreements → the expectation is captured at
the moment of disagreement. For curators who will never open a pull request, this is the only
path that works, and it could grow into the triage frontend in #65.

## What it does that git files cannot

So that this is not a strawman:

- Stamp each expectation with the `babel_version` it was observed against, automatically,
  from `/status` (which `generate_report.py` already fetches). In git the contributor has to
  type it.
- Bulk re-baselining after a Babel release, with a review queue. The "624 rows" problem in
  [git-files.md](git-files.md) is a database operation; the git equivalent is a tool nobody
  has written.
- Hold licensed or personal inputs unpublished while exporting only what we may publish. A
  private repo still puts the data in every collaborator's clone and in Actions logs.
- A no-git edit loop.

## Why it should not be the source of truth

- It is new infrastructure with users — authentication, a database, deployment, backups,
  uptime — on a project that is currently zero-infrastructure (Actions and Pages) with one
  developer. The "nightly run depends on a service being up" objection is only partly fair:
  the run already depends on GitHub search, Google and six deployments. The ops burden is
  the real cost.
- Everything in it is untrusted and editable by any account holder, with no review unless we
  build a review queue. That is the sheet's problem again, with a login in front of it.
- Uploaded text lands on a public website at scale, and the licensing and privacy of uploaded
  data become our problem.
- Bulk runs load the shared NodeNorm and NameRes instances.

## The cheap version

A static, client-side page in `website/`: upload a CSV in the browser, call NodeNorm and
NameRes directly, flag rows, download a records YAML or a prefilled issue body. No backend, no
database, git stays the source of truth, and it finds out whether anyone actually wants the
workflow before we pay for a hosted one.

`babel-explorer` was the assumed home for this; it is not a fit. It is a Python tool for
querying and exporting Babel's intermediate files, not a UI.
