# The Babel Milestones page

<https://translatorsri.github.io/babel-validation/milestones/> — regenerated daily by
[`milestones-page.yaml`](../.github/workflows/milestones-page.yaml) from
[`milestones_page.py`](../src/babel_validation/tools/milestones_page.py).

## The problem

Babel work is spread over five repositories in two organizations (Babel, NodeNormalization,
NameResolution, babel-validation, babel-explorer). Milestones are the commitment mechanism —
when something needs dealing with by a soft deadline, it goes in a milestone — but milestones
cannot span repositories, so "what have I committed to?" means visiting five separate pages.

## Why a generated page rather than a project board

A GitHub Project spanning the repositories was the obvious alternative, and was rejected:

- **A board is a second record of commitment.** It has to be kept in step with the milestones
  by hand, and it drifts the moment that stops happening. This page is *derived* — the
  milestone is the only input, so there is nothing to keep in sync.
- **Boards can't answer the outside question.** The most useful thing here is telling someone
  who filed an issue roughly when it'll be looked at. A public URL does that; a board does not.
- **Automating a board is expensive.** The built-in auto-add workflow filter supports only
  `is`/`label`/`reason`/`assignee`/`no` — not `milestone:` — and never removes items, so
  keeping a board in step with milestones needs an Action in all five repositories listening
  for `milestoned`/`demilestoned`, plus a PAT with `project` scope stored as an organization
  secret in both organizations.

What is given up: manual rank-ordering within a milestone. A `priority:` label is the
intended substitute, since labels are readable with the same token as everything else.

## Constraint worth preserving

Every repository listed is public, so a workflow's built-in `GITHUB_TOKEN` can read all of
them across both organizations — no secrets to configure or rotate. Reading anything off a
GitHub Project would break this, because `project` scope requires a PAT. Keep priority and
component in labels.

## Publishing alongside the website

`gh-pages` is shared. `deploy-website-to-gh-pages.yaml` deploys `website/dist` to the root of the
branch and cleans by default, so this page is only safe because `milestones/` is listed in that
job's `clean-exclude`. Anything else published to `gh-pages` needs the same treatment.

## Not done yet

- Priority/component labels aren't surfaced or sorted on — all labels render undifferentiated.
- Closed milestones are ignored, which hides ~253 open Babel issues parked in closed
  milestones (`Needed soon`, `Needs tests`, `Needs investigation`, …).
- No grouping by repository or component; one flat chronological list.
- The legacy priority-bucket milestones are recognised by title in `BUCKET_TITLES`. If they
  get cleaned up, drop that list.
