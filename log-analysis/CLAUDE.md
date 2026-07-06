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

## Data & git hygiene

- **Raw log exports and generated artifacts are not committed.** gitignore the
  log files, any generated `benchmark/` output, and marimo's `__marimo__/`
  session cache (output snapshots, regenerated on run). Commit only the
  notebook `.py` source + supporting code.
- Make small, logical commits as the notebook grows (loader → stats → viz →
  export), not one giant commit.
