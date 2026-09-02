# CLAUDE.md — log-analysis (marimo notebooks)

Guidance for working on the log-analysis notebooks (`nameres/`, `nodenorm/`).
These are pair-programmed as **live marimo notebooks** via the `marimo-pair`
skill. Read this before editing a running notebook.

## Environment

- This project runs everything through **`uv run`** — never invoke `.venv`
  directly and never `pip install`. Dependencies live in the repo-root
  `pyproject.toml`; `cm.packages.add(...)` goes through uv and updates
  `pyproject.toml` + `uv.lock` (commit those changes with the notebook work).
- marimo is a dev dependency (`marimo[recommended]`), which brings in `altair`.
  `pandas`/`numpy` are declared project dependencies.

## Driving a live marimo notebook

- **The running kernel is the source of truth.** During a live session, do NOT
  edit the notebook `.py` file with Edit/Write — changes won't reach the kernel
  and may be overwritten. Make all cell changes through `marimo._code_mode`
  (`cm`) using the marimo-pair skill's `execute-code.sh`.
- `execute-code.sh` resets the shell cwd after each call — always use
  **absolute paths** in the surrounding Bash, and read/write project files with
  paths relative to the notebook's kernel cwd (the notebook directory).

### `cm.get_context()` gotchas (learned the hard way)

- **Never touch a just-created cell inside the same `async with` block.** A cell
  created via `ctx.create_cell(...)` is not queryable (`ctx.cells[new_id]`
  raises `KeyError`) until the context exits. Worse: **if the block raises, the
  entire queued operation is discarded** — so a stray `print(ctx.cells[new_id])`
  will silently roll back your `create_cell` + `run_cell`. Capture the returned
  id in a plain variable, exit the block, then inspect in a separate call.
- `create_cell` / `edit_cell` only change structure; queue `ctx.run_cell(...)`
  to actually execute.
- `create_cell` defaults to `hide_code=True`. Pass `hide_code=False` for code
  cells you want visible (markdown/header cells can stay hidden).
- `ctx.screenshot(...)` is an async method **and requires Playwright**, which is
  not installed here. Verify cells instead by checking `ctx.cells[name].status`
  (want `idle`) and `.errors` (want `[]`), and by inspecting data in the
  scratchpad. Pure-markdown (`mo.md`) cells often report `stale` — harmless.

### marimo graph rules

- No cycles; each public name has exactly one owning cell; no wildcard imports.
- Use `_private` names for same-cell intermediates so they don't enter the
  dataflow graph. Reassigning a public name in another cell fails with
  "Multiply-defined names".

## Visualizations

- Prefer marimo-native interactive charts: **Altair** + `mo.ui.*` controls
  (dropdown/checkbox/slider) read via `.value` in a dependent cell. Static
  matplotlib is fine when easier.
- Altair embeds at most 5,000 rows by default; call
  `alt.data_transformers.disable_max_rows()` for larger datasets.

## Paths inside a notebook

- **Never use a cwd-relative path.** marimo inherits the cwd of whatever
  launched it, so `Path("output")` resolves next to the notebook when opened
  from its own directory and at the repo root when opened from there. That is
  how generated artifacts end up outside the `log-analysis/<service>/.gitignore`
  written to catch them — silently, because both spellings "work".
- Anchor on `mo.notebook_dir()` instead: outputs under
  `NOTEBOOK_DIR / "output"`, shared inputs under
  `NOTEBOOK_DIR.parents[1] / "data" / ...`.

## Testing notebook logic

Notebooks are not importable as modules — the `log-analysis` directory has a
hyphen in it and cells are `@app.cell` functions, not module-level defs. But
they *are* loadable by path, and marimo's `Cell.run()` executes one cell plus
its ancestors and hands back its definitions:

```python
spec = importlib.util.spec_from_file_location("nb", NOTEBOOK)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module          # marimo resolves annotations via sys.modules
spec.loader.exec_module(module)
_output, defs = module.parser.run()      # -> {"parse_record": ..., ...}
```

This only works for cells that touch no data, since the log exports are not
checked in. So **keep pure helpers in their own cells**, separate from the cell
that loads or transforms the data — `span_helpers` and `chain_helpers` in
`nameres/analyze_nameres_logs.py` exist for exactly this reason. Tests live in
`tests/log_analysis/`.

## Sharing a notebook (exports)

The notebook `.py` is the **only** editable source. Everything below is a
generated snapshot: regenerate it, never edit it, and never treat an edit made
to an export as work to merge back.

Export to a single self-contained HTML file, into the notebook's `exports/`
directory, with a `.generated.` infix in the filename:

```bash
uv run marimo export html log-analysis/nameres/analyze_nameres_logs.py \
  -o log-analysis/nameres/exports/analyze_nameres_logs.generated.html -f
```

That is enough for current needs; wrap it in a script when there is more than
one notebook to export.

- **HTML is the default format**, because it opens in any browser with nothing
  installed and cannot be forked by accident. `marimo export ipynb
  --include-outputs --sort top-down` also produces a genuinely readable Jupyter
  notebook (`mo.md` cells become real markdown cells), but hand it out only when
  someone has said they want to run the numbers themselves — an `.ipynb` invites
  editing, and edits to it are lost work. Use `--sort top-down`, not the default
  `topological`, so the title cell stays first.
- **`marimo export html` runs the notebook**, so it needs the log exports on
  disk. Nobody without a populated `data/log-analysis/` can regenerate one.
- **`exports/` is gitignored, and must stay that way.** The rendered outputs
  embed every query string real users typed. Share exports out of band (e.g. a
  shared Drive), not through this repo.
- **Keep infrastructure identifiers out of any frame that gets rendered whole.**
  `df` is displayed in full, so it is the one place a parsed field reaches the
  export; every other displayed table names its columns explicitly. `pod_name`
  and `image_tag` are parsed onto `entries` and dropped from `df` for exactly
  this reason. After changing what a rendered frame contains, re-export and grep
  it before sharing.

## Data & git hygiene

- **Raw log exports and generated artifacts are not committed.** gitignore the
  log files, any generated `benchmark/`/`output/` artifacts, and marimo's
  `__marimo__/` session cache (output snapshots, regenerated on run). Commit
  only the notebook `.py` source + supporting code.
- The repo-root `.gitignore` needs **both** `data/` and `data`: the first
  matches a real directory, the second also matches a worktree's symlink to a
  shared one. `data/` alone leaves the symlink showing as untracked.
- Make small, logical commits as the notebook grows (loader → stats → viz →
  export), not one giant commit.
