# Suggested staging

1. **#149, with the loader designed for more than one source.** A `load_records(path)` that
   mints ids, keeps provenance (category, source, source URL), and carries per-mode and
   per-target expectations with a reason and an optional `babel_version`, plus a `public`
   flag. A records executor grown from the two `*_from_gsheet.py` tests. A new dashboard
   `kind`. #100 closes alongside, since parsing is no longer tied to fetching.
2. **`sources/<team>/` with `CODEOWNERS`** as the contribution path; `csv-to-babeltests`
   (#77, #104) retargeted to emit records; a CONTRIBUTING section that says how.
3. **A submodule and an adapter for `NCATSTranslator/Tests`** (#35): SHA-pinned, Dependabot
   bumps, the expectations overlay and non-strict xfail, a global run budget.
4. **The client-side workspace page** in `website/`, as an exporter. Only then decide whether
   a hosted app with a database earns its operating cost.

# Open questions

- Is there a second contributor besides the Test Harness team to design step 2 around?
- Should the overlay live only in this repo, or may a contributor's own file carry
  per-target expectations too — and if both, which wins?
- Non-strict xfail for foreign sources, or version-stamped expectations? The second is more
  information and more to write down.
- Does anyone on the Translator side want the distributed-runs model — running our harness in
  their repo against their file?
- Are the Tests repo's `input_id` values NodeNorm output? That decides whether the NodeNorm
  half of that adapter is a regression guard or a real test.
