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
  back to the real path, so the globs and the list see the file's own name. The selection is computed in each
  round from that round's diff; `ariane verify` selects the same way from the base to the head.
- **Configuration changes select everything.** A change to `ariane.toml`, or to a file matching
  the new `[project] check_all_paths` globs (lock files, CI files), selects every check.
- **The list for the check.** Every check that runs gets `ARIANE_CHANGED_FILES`, the absolute
  path of `work/<n>/changed-files.txt` in its own replay tree, listing the changed files one per
  line relative to the repository root. Ariane does not interpret it: a check may use it to run
  only the related tests. The variable is added after the environment is built (it is not a
  `[project] env` entry). The file is written just before the check and removed after it, so the
  replay tree is verified clean as before; it is never written through a folder leading outside
  the tree, nor over a file the commit holds (that stops the replay). It is removed only while it
  is still the file written, in the same folder: a check that moves the folder, or replaces it by
  a link leading outside the tree, leaves it to the tree's removal, and no file outside is touched.
- **Records and statuses.** A skipped check is a result with `skipped` set, which passes: it never
  blocks. `checks.md` shows it as `skipped` in the summary table with the reason "no changed file
  matches `paths`", the journal names the skipped checks (`ticket.checks.skipped`), the commit
  status is a `success` described "skipped by Ariane: no changed file matches `paths`" (so a
  required status does not block the pull request), and the pull request body and the reviewer's
  prompt list the skipped checks.
- **One read of the diff per round.** The round's `git.changes` is read once by the replay and
  reused by the review (`replay.round_changes`): the git process moves from the review phase to the
  replay phase of ADR 0053's counts, and the total per round is unchanged.

## Consequences
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
