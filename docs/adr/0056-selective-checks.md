# 0056. Selective checks

- Status: accepted
- Date: 2026-10-20
- Capabilities: C9, C10, C11

## Context
Every ticket replayed every check, whatever it changed: a one-line documentation fix waited for
the whole test suite, and with several tickets at once the replays queued up. C9 asks for
deterministic checks Ariane runs itself; it does not ask for every check on every change. A
project knows which files each check covers; Ariane knows which files a ticket changed.

## Decision
- **A check's scope.** `checks[].paths` is an optional non-empty list of path globs (the rules of
  `not_run_locally`, ADR 0042). The check is selected when at least one changed file matches.
  `checks[].always = true` selects it always, which is also the default without `paths`; `always`
  accepts only `true`, and `paths` with `always` is refused naming `checks[<i>]`. The
  documentation checks (`documentation.generated`) are always selected.
- **Changed files.** The diff from the ticket's start commit to the replayed commit, without
  `work/` (Ariane's records), read from `git diff --raw` (`git.changes`): a rename or copy counts
  on both sides, so a check covering the old path still runs. A path git quotes (one holding a
  double quote, a backslash or a control character, even with `core.quotepath=off`) is decoded
  back to the real path, so the globs and the list see the file's own name; a glob's `*` and `**`
  match a line break in it too. The selection is computed in each
  round from that round's diff; `ariane verify` selects the same way from the base to the head.
- **Configuration changes select everything.** A change to `ariane.toml`, or to a file matching
  the new `[project] check_all_paths` globs (lock files, CI files), selects every check.
- **The list for the check.** Every check that runs gets `ARIANE_CHANGED_FILES`, the absolute
  path of `work/<n>/changed-files.txt` in its own replay tree, listing the changed files one per
  line relative to the repository root. Ariane does not interpret it: a check may use it to run
  only the related tests. The variable is added after the environment is built (it is not a
  `[project] env` entry). The file is written just before the check; it is never written over a
  file the commit holds nor through a link (that stops the replay). With parallel checks another
  check may move or replace a folder at any moment, so a path checked first and used after is not
  enough: on POSIX each folder of `work/<n>/` is opened by handle without following a link, and
  the file is created relative to the last handle. On Windows, whose Python standard library has
  no such calls, the same steps go by path, checked before: a narrower guarantee, accepted because
  the check already runs with the user's rights. Ariane never removes the file by name after the
  check: what is at that name then may not be the file it wrote (a check can swap it), and no
  check of a name before removing it is atomic. The replay tree is removed after each check
  anyway, the file with it; until then the tree's verification leaves out that one path
  (`checks.without_listing`), whatever a check left there.
- **Names the list cannot hold.** Git ends each record of a listing at a line feed only, so the
  listings are split at line feeds, never at the other separators Python's `splitlines` knows
  (U+2028, a form feed): a name holding one stays whole. A changed path whose name holds a line break would read as two
  paths in a one-per-line list: the replay stops before any check, naming it, rather than give a
  check an ambiguous list. Such names are rare and a NUL-separated list would surprise the usual
  tools (`vitest related`, `xargs`).
- **Records and statuses.** A skipped check is a result with `skipped` set, which passes: it never
  blocks. `checks.md` shows it as `skipped` in the summary table with the reason "no changed file
  matches `paths`", the journal names the skipped checks (`ticket.checks.skipped`), the commit
  status is a `success` described "skipped by Ariane: no changed file matches `paths`" (so a
  required status does not block the pull request), and the pull request body and the reviewer's
  prompt list the skipped checks.
- **One read of the diff per round.** The round's `git.changes` is read once by the replay and
  reused by the review (`replay.round_changes`): the git process moves from the review phase to the
  replay phase of ADR 0053's counts, and the total per round is unchanged.

**Accepted residual (owner, 20 October 2026).** The listing's containment holds against a
link met on the way and a file the commit holds, not against another check of the same run
moving a folder of `work/<n>/` out of the replay tree after Ariane opened it and before the file
is created: the descriptor follows the moved folder, so the new listing (a list of paths, never
written over a file) lands where that check moved it. Only a check of the project, running with
the user's rights, can do this, and it could write that file itself; closing it needs an
operating-system sandbox, as the residuals of ADR 0017, and waits for slice 7.

**Amendment: the risk tier of a round (#185).** Selection by `paths` skips the checks a ticket
cannot affect; the risk tier sizes how much of each selected check runs.
- **The tier.** Before its checks, each round gets a tier, `low` or `high`, from the same diff
  (start commit to replayed commit, without `work/`; `ariane verify`: base to head) and the
  optional `[checks_policy]` table (`risk.ChecksPolicy`, computed by `checks.risk_tier`). It is
  `high` when any of these holds, each recorded as a reason: more than `max_changed_lines` lines
  added and removed (default 300, `git diff --numstat` as in ADR 0046); more than `max_modules`
  modules touched (default 3); a changed file matching `critical_paths`; a change to
  `ariane.toml` or to a `check_all_paths` file; a previous round of the same ticket failed a
  check (any check, blocking or not, not a skipped one). It is `low` otherwise, with the counts as
  its reason. Without the table every round is `high` (reason "no `[checks_policy]`"): no
  behaviour change.
- **Modules.** `module_roots` lists globs of folders (`"src/*/"`); a changed file's module is
  the deepest matching root and the file's first path segment below it, and a file under no root
  counts as no module (documentation and tests beside the code do not widen the reach). Without
  `module_roots`, the repository root is the only root: the module is the first path segment.
- **Effect.** Every check gets `ARIANE_RISK_TIER=low|high` and `ARIANE_FULL_SUITE`: `1` when the
  tier is `high` or the check declares `full_when = "always"`, else `0` (`full_when` defaults to
  `"high"`). Selection by `paths` still comes first. The project's command decides what a
  related-tests run is; Ariane picks no test.
- **Records.** `checks.md` starts with "Risk tier: <tier>: <reasons>."; the journal logs
  `ticket.checks.risk_tier`; the pull request body and the reviewer's prompt state it.
- **Review sizing (ADR 0046).** A `high` tier measured by `[checks_policy]` keeps the full
  review even when the diff is within `[agents.reviewer.small] max_lines`; the journal's
  `ticket.review.started` then says "risk tier high: full review". The tier without the table is
  not measured and leaves the sizing by lines as it was, so a configuration without
  `[checks_policy]` behaves exactly as before.
- **Why from the diff, not from the implementer.** The implementer is the party whose work is
  being checked: a tier it declares could be lowered to skip tests. The diff is what Ariane
  already reads for the selection, it is deterministic (C9), and the same commit always gets the
  same tier.
- **Why a failed round forces `high`.** A failed check shows the change broke something its
  related tests may not cover; the fix that follows is small by construction, so a size threshold
  alone would let the fix round run fewer tests than the round that failed.
- **Why these defaults.** 300 changed lines and 3 modules are about the size of one coherent
  feature in one area; above either, the related tests are less likely to cover what the change
  reaches. Both are the project's to tune.
- **Choosing the implementer's model from the tier** is not done: it needs measurements on the
  benchmark first.
**Amendment: the sampled full replay and the escape rate (#186).** Selection by `paths` and a
`low` tier save replay time by running fewer tests; that is only safe if what they miss is caught
and measured.
- **When.** When the last round of a ticket passed its blocking checks with at least one check
  skipped or run with `ARIANE_FULL_SUITE=0` (`checks.partial_names`), Ariane decides from
  `[checks_policy] full_replay_sample` (a number from 0 to 1, default 0.2; 0 disables it) whether
  to run a full replay (`full_replay.after_delivery`): every check, the documentation checks too,
  with `ARIANE_RISK_TIER=high`, `ARIANE_FULL_SUITE=1` and `ARIANE_CHANGED_FILES`, each in a fresh
  replay tree of the replayed commit, verified by the guard as a round is (git and the remote as
  the delivery left them are the baseline). The defaults also apply without the table: a project
  with `paths` but no `[checks_policy]` is sampled at 0.2; one with neither skips nothing and runs
  nothing partly, so nothing changes for it.
- **The draw.** The first 8 bytes of SHA-256 of "ariane full replay <n> <commit>", read as an
  integer, below `full_replay_sample` × 2⁶⁴: deterministic for a ticket and its replayed commit, so
  a rerun gives the same choice, and spread evenly over the tickets.
- **Escapes.** A check that fails in the full replay although it passed, or was skipped, in the
  last round is an escape; one that failed there already is not. Each is written to
  `work/<n>/full-replay.md` (every check's selective and full result, the escapes' outputs, redacted
  by the ticket folder), journaled `ticket.checks.escape`, commented on the pull request naming the
  checks (redacted), and published as a failing `ariane/full-replay` status on the pushed commit;
  a full replay without an escape publishes a success. A check that failed before a later one
  stopped the full replay is still an escape, recorded and published (the stop is recorded after
  it); a stop before any escape publishes no status. A check may not be named `full-replay`: a
  check is published as `ariane/<name>`, and the full replay's success would replace that check's
  failure on the same commit. A refused status or comment is a journaled
  warning. The records go in one local commit, "record the full replay", which, like the record of
  the pull request, is not pushed.
- **Measures.** `metrics.json` (the ticket's measures file, ADR 0034) gains `replays`, per round
  the checks selected, skipped and partial and the replay's duration, and `full_replay`, whether it
  ran, its duration and its escapes (`stopped` with the reason when it stopped).
- **Report.** `ariane report` adds a "Selective checks" line: the tickets with selection and their
  replay time, the last round's replay time against the full replay's on the sampled tickets (the
  time saved), the full replays, the escapes and the escape rate, escapes (failing checks, summed)
  / full replays, then a warning when the rate is above `[checks_policy] max_escape_rate` (default
  0.02). A stopped full replay is not counted, nor its escapes: they are in its record, its
  journal, its status and its comment.
- **Why after delivery.** The full replay is a measure, not a gate: the project's CI still runs
  everything on the pull request and stays the safety net. Run before the push, it would cost the
  full replay's time on every sampled ticket, the time selection is meant to save, and a sampled
  ticket would be delivered differently from the others. After the delivery it never delays or
  changes the push, the pull request, its body or the review, and the run's outcome and line stay
  those of the delivery; a stop or Ctrl-C during it, or an error while recording, publishing or
  committing its records, is journaled when it can be and ends only the full replay. Those
  records are committed only in the ticket worktree, after the push, so `ariane report` reads the
  ticket worktrees too: a worktree's record replaces the merged record of the same run.
- **Why sampling, not every ticket.** A full replay on every ticket would double the replay time
  of each selective ticket and remove the saving; a fifth of them is enough to estimate a rate
  over a few dozen tickets, and the project tunes the fraction (1 during a trial, lower once the
  rate is known).
- **How the rate decides.** The owner keeps selection on while the escape rate stays at or below
  `max_escape_rate`; above it the report warns, and the owner widens `paths`, raises the
  `full_when` of a check, tightens `[checks_policy]` or removes selection. Ariane never turns it
  off by itself, and does not read the project's CI results to count escapes (a later CI feedback
  loop).

A project that declares `paths` waits only for the checks a ticket can affect. A wrong `paths`
lets a change through untested by that check; the project's own CI still runs everything on the
pull request. Existing configurations, without `paths`, keep running every check. Ariane's own
`ariane.toml` declares no `paths` yet.

## Alternatives considered
- **Select only what `paths` lists, by default.** A check without `paths` would never run, or
  every existing configuration would have to be edited; the default stays "all".
- **Let a configuration change go through the globs.** A changed lock file, CI file or check
  command can break any check, even one whose files did not change; selecting everything is the
  simple, safe answer.
- **The changed files in the variable's value.** A long list exceeds the environment size limits,
  on Windows especially (32,767 characters for one variable); a file has no such limit, and is
  read the same way on every platform.
- **Interpret the list in Ariane (pick tests itself).** That ties Ariane to each test runner; the
  check's own tooling (for example `vitest related` or a pytest plugin) knows its tests better.
