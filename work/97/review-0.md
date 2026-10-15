# Review 0

- Reviewed commit: `810844ef3ebfd01c18ac1a9e542d6cc00a353ec7`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/metrics.md:23`) Collaboration arrow `shadow --> metrics` does not exist in the code

  metrics.md adds `shadow --> metrics`, but src/ariane/shadow.py does not import `ariane.metrics`; it only sets `self.metrics.mode` on the inherited run. shadow.md and 3-components.md (correctly) leave this arrow out. The three diagrams disagree with each other. Either remove the arrow from metrics.md or add it everywhere.

- **minor** (`src/ariane/cli.py:158`) No test for the `--shadow` CLI dispatch

  `_start(root, number, shadowed)` picks `shadow.start` when `--shadow` is given, but no test in tests/test_cli.py runs `main(["start", "--shadow", ...])`. A regression in the argument wiring (for example, always calling flow.start) would deliver a real push and pull request while the user believes they are in shadow mode, and every shadow test would still pass because they call shadow.start directly.

- **minor** (`src/ariane/shadow.py:72`) Missing `origin/<base>` stop path not tested; a failed clone leaves a partial clone

  The "run `git fetch origin`" stop has no test. If `git clone`, `remote remove` or `checkout` fails after the clone directory is created, the leftover directory makes the next run stop with "remove it to start over" and no hint about the earlier failure. This is acceptable but untested.

- **minor** (`src/ariane/attempts.py:67`) Counting heuristic misses common wrappers

  `sudo git push`, `env git push`, `command git push`, `time git push`, `xargs git push` and `git push` inside `$(...)` are not counted, because only the first word (after VAR=value assignments) is checked as the program. ADR 0036 records shell parsing as a heuristic, so this is not blocking. Skipping a short list of transparent wrappers (env, command, time, sudo, nohup) would be cheap.

- **minor** (`tests/test_c19_attempts.py:46`) Adapter `run` paths that put attempts on SessionResult are not exercised

  The tests feed TokenTally.add_line and Events.add_line directly. They never check that `ClaudeCodeRuntime.run` (the dataclasses.replace wrapper, including the budget/stopped path) or opencode's `Events.result()` actually carry `attempts` into SessionResult. The metrics test uses a FakeRuntime that sets attempts itself.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  tests/test_c19_shadow.py has 6 tests and tests/test_c19_attempts.py has 9 parametrized cases plus 4 tests. They import `ariane.shadow`, `ariane.attempts`, `SessionResult.attempts` and the metrics `attempts` key, none of which exist before the change, so they fail without it. Together they cover: no PR or status, `.git` byte-identical plus worktree list, no origin, the exact final line, the existing-clone stop, git push / gh pr create counted, pushd and quoted echo not counted, counts reaching metrics.json, and a guard violation counted. That is more than 7 tests. Gaps (CLI flag, adapter run paths) are listed as minor findings.

- met: The documentation the change affects is updated (C25).

  Added: modules/shadow.md and modules/attempts.md. Updated: flow.md, claude_code.md, opencode.md, metrics.md, runtime.md, cli.md and 3-components.md. Regenerated: docs/reference/cli.md (--shadow) and docs/logs.md (ticket.shadow.done). README explains shadow mode with PowerShell and bash blocks. modules/logs.md, flagged as untouched, describes only generic declarations and points to the regenerated catalogue, so it needs no change. One wrong arrow in metrics.md is listed as a minor finding.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0036-shadow-mode-and-attempts.md records the choices the spec leaves open: --no-checkout plus base cut at the last fetched origin/<base> with no fetch; `refs/remotes/shadow/<base>` naming; ShadowRun as a subclass with no remote check; exit 0 and outcome `delivered`/`needs a human`; shlex-based counting with sh -c followed and global options skipped; guard violation defined as a Stop raised by verify; and alternatives considered.

## Proposed learnings (not decided)

- When a mode must never deliver (shadow, dry-run), test the CLI flag wiring end to end, not only the module entry point: a miswired flag silently turns a no-push run into a real push.
- Module collaboration diagrams are duplicated across the module docs and the component view; check that an added arrow matches a real import and appears in every diagram that lists it.
