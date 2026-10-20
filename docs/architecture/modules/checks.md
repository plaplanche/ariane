# Module `ariane.checks`

Runs the deterministic checks of `ariane.toml` itself and never believes an agent. It also renders the results as a summary line, a table and a committed report.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `PASSING_OUTPUT_LINES` | constant | How many output lines a passing check keeps in the report. |
| `CHANGED_FILES_VARIABLE` | constant | `ARIANE_CHANGED_FILES`: the variable naming the list of changed files a check gets (ADR 0056). |
| `CHANGED_FILES` | constant | `changed-files.txt`: that list's file name, in the replay tree's ticket folder. |
| `SKIPPED` | constant | The reason recorded for a check not selected: no changed file matches `paths`. |
| `CheckResult` | dataclass | Outcome of one check: `name`, `command`, `blocking`, `passed`, `detail`, `output`, `duration_s`, `not_run_locally` (the globs the check declares, ADR 0042), `skipped` (not selected, so not run; `passed` is true, ADR 0056). |
| `changed_files(name_status)` | function | The paths of a `git diff --name-status` listing, split at line feeds only (a name holding U+2028 stays whole), a rename or copy counted on both sides, each decoded by `git_path`. |
| `git_path(name)` | function | The real path behind a path as git prints it: a quoted one (a double quote, a backslash or a control character in it, even with `core.quotepath=off`) is unquoted and its octal escapes decoded as UTF-8 bytes. |
| `unlistable(changed)` | function | The changed paths whose name holds a line break: the line-delimited listing cannot hold them, so the replay stops on them (ADR 0056). |
| `changed_files_listing(tree, records, changed)` | context manager | `<records>/changed-files.txt` in `tree`, listing `changed` one per line, made new for the block and never removed by name (the replay tree's removal takes it); on POSIX each folder is opened by handle without following a link and the file made relative to the last one, on Windows by path (ADR 0056). |
| `without_listing(status, records)` | function | A replay tree's `git status --porcelain` without the listing's path (and anything under it, if a check put a folder there): what the post-check verification compares (ADR 0056). |
| `selected(all_checks, changed, check_all_paths)` | function | The checks a change selects (ADR 0056): every one when it touches `ariane.toml` or a `project.check_all_paths` file, else those without `paths` and those whose `paths` match a changed file. |
| `skipped_result(check)` | function | The `CheckResult` of a check not selected. |
| `skipped_names(results)` | function | The names of the skipped checks. |
| `run_checks(checks, cwd, env)` | function | Runs the declared checks in a working tree, in order. |
| `run_check(check, cwd, env)` | function | Runs one check and returns its `CheckResult`. |
| `blocking_failures(results)` | function | The blocking checks that did not pass. |
| `summary_line(results)` | function | One line: how many checks passed and which blocking ones failed, and how many were skipped when some were. |
| `summary_table(results)` | function | A Markdown table of the results; a skipped check shows `skipped`. |
| `unrun_files(results, changed)` | function | The changed files matching a check's `not_run_locally` globs. |
| `report(results, commit, changed=())` | function | The committed `checks.md` text for a commit, with the globs a check does not run and the matching changed files, and each skipped check with its reason; it says each check was replayed in its own clean working tree, after the setup. |
| `parse_summary_table(text)` | function | Reads a committed report back as (name, blocking, outcome) tuples; a skipped check counts as passed. |

## Behaviour and errors

- `CheckResult`: name, blocking flag, outcome and output of one check.
- `run_checks`, `run_check`: run the declared commands in a working tree; `run_check` is called from the replay's worker threads when `project.parallel_checks` is above 1 (ADR 0052), each with its tree and its slot's environment; the flow also passes the generated-documentation commands as checks named `docs: <name>` (C25), so they appear in the report and the statuses like any check.
- A check runs after its tree's dependency caches were copied from the store or built (`[[project.cache]]`, ADR 0054) and after its setup; neither is part of its duration, and its report is the same with or without caches.
- `selected`, `skipped_result`: the replay runs only the selected checks and records the others as skipped (ADR 0056); a skipped check never fails, so it never blocks. `changed_files` turns the round's `--name-status` listing into the changed files the selection and `ARIANE_CHANGED_FILES` use.
- `changed_files_listing`: the listing a check gets. On POSIX (`os.supports_dir_fd`), the tree is opened, then each folder of `records` is made if missing and opened with `O_DIRECTORY | O_NOFOLLOW` relative to the previous one; the file is created with `O_EXCL | O_NOFOLLOW` in the last folder's handle. Ariane never removes it by name: a check could have swapped it, and the replay tree is removed after each check anyway. Another check that moves or replaces a folder on the way at any moment (parallel checks, ADR 0052) therefore never makes Ariane create a file outside the tree: a link met on the way, or a file the commit holds, stops with "the replayed commit holds work/<n>/changed-files.txt, or its folder leads outside the replay tree". Windows has no such call in Python's standard library: there the folder is checked inside the tree before it is made, a narrower guarantee.
- `blocking_failures`, `summary_line`, `summary_table`, `report`: read and render results.
- `parse_summary_table`: read a committed report back.

## Workflow

```mermaid
flowchart TD
  A[run_checks checks, cwd, env] --> B[run_check for each check]
  B --> C[run the command in cwd]
  C --> D{timeout, missing command or non-zero exit?}
  D -- yes --> E[CheckResult passed False, with detail]
  D -- no --> F[CheckResult passed True]
  E --> G[list of results]
  F --> G
  G --> H[blocking_failures]
  G --> I[summary_line]
  G --> J[report commit] --> K[summary_table]
  L[parse_summary_table text] --> M[name, blocking, outcome tuples]
```

## Code view (C4 level 4)

```mermaid
classDiagram
class CheckResult {
  <<dataclass>>
  name str
  command tuple
  blocking bool
  passed bool
  detail str
  output str
  duration_s float
  skipped bool
}
class checks {
  <<module>>
  run_checks(checks, cwd, env) list
  run_check(check, cwd, env) CheckResult
  changed_files(name_status) list
  git_path(name) str
  unlistable(changed) list
  without_listing(status, records) str
  changed_files_listing(tree, records, changed) Iterator
  selected(all_checks, changed, check_all_paths) list
  skipped_result(check) CheckResult
  blocking_failures(results) list
  summary_line(results) str
  summary_table(results) str
  report(results, commit) str
  parse_summary_table(text) list
}
checks ..> CheckResult
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  checks --> config
  checks --> process
  checks --> stop
  checks --> ticket
  delivery --> checks
  flow --> checks
  replay --> checks
  review --> checks
  review_session --> checks
  shadow --> checks
  verify --> checks
```
<!-- end generated -->

## Serves

C9, C21, C25; ADR 0004, ADR 0018, ADR 0026, ADR 0054, ADR 0056. See [the component view](../3-components.md).
