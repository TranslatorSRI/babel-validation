# Alternatives considered

- **Just pull requests to this repo's YAML, no federation.** The YAGNI version. Mechanism (a)
  in [git-files.md](git-files.md) is this plus `CODEOWNERS`; the only difference is who
  reviews.
- **Distributed runs.** A reusable Actions workflow each team runs in their own repo against
  their own file; our dashboard aggregates their `report.json`. Puts ownership and load with
  the contributor. Costs an aggregation format, a token per team, and a public-site trust
  problem per team. Worth revisiting if a contributor wants to own their runs.
- **Multiple Google Sheets.** Rejected: a runtime dependency on Google, a secret ID per sheet,
  no review, validation of arbitrary spreadsheets. Converting a sheet once is fine — see (c)
  in git-files.md.
- **Versioned dataset artifacts.** A GitHub release asset with a checksum in a lockfile. How
  the Tests repo would most naturally be consumed if a submodule turns out awkward; it needs
  mechanism (d)'s fetch-and-cache machinery.
- **Issue attachments.** A CSV attached to a BabelTest issue extends the existing
  untrusted-issue model with no new source type, but hits the 1,000-parameter cap immediately.
- **Adopt Translator-wide test assets** rather than import from them. Not yet: their assets
  are edge-shaped (subject, predicate, object) and ours are node-shaped.
- **Tests next to the thing tested**, in `NCATSTranslator/Babel` (cf. Babel #916). Puts the
  files where Babel developers live, but Babel's repo is the pipeline, and the harness would
  become a dependency of it.
