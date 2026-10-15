# Review 0

- Reviewed commit: `5d0226d856c6c8705c6df3d9fea7b0c439d20f50`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/3-components.md:57`) Component view not updated with the new shadow dependencies

  docs/architecture/modules/shadow.md now draws `shadow --> metrics` and `shadow --> ticket`, but the component view at docs/architecture/3-components.md:57-60 still only has shadow → flow/git/stop/tracker. Rule 11 says the C4 level files should be updated too. The diagram was already incomplete before this change (shadow → checks and shadow → review are also missing), so this is drift, not a regression.

- **minor** (`src/ariane/shadow.py:152`) Corrupt metrics.json gives a traceback, not one line

  `json.loads(path.read_text(...))` has no guard. If the clone's metrics.json is truncated, edited by hand or not valid JSON, `ariane judge` crashes with a JSONDecodeError traceback. The spec's "one line" contract (C23) isn't kept on that path. Also, a clone that exists but has no metrics.json is reported as "no shadow clone for it", which is wrong for that case.

- **minor** (`README.md:92`) README paragraph line not wrapped like its neighbours

  The changed line 'work/12/ to read. Remove the clone ... how long it took' is about 117 characters long. The surrounding paragraph wraps at about 100. This is cosmetic only.

- **minor** (`docs/adr/0037-judge-command.md:21`) Judgement is lost if metrics.json is rewritten later; this is only acknowledged

  The judgement is written to the working tree and never committed. Any later rewrite of metrics.json by Ariane would drop it: for example a re-run, or `git checkout`/`git restore` in the clone. The ADR says 'a shadow ticket is not run again once judged', but nothing enforces that. The shadow `start` path does refuse an existing clone, which makes the risk small. The next ticket, where report reads judgements, should keep this in mind.

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

  tests/test_c19_judge.py adds 7 `test_c19_judge_*` tests, one of them parametrized 5 ways, so there are 11 cases. They call `shadow.judge` and `cli.main(["judge", ...])`, which don't exist before the change, so every test fails without it. They cover: accept with minutes and note; reject with a null note; unknown ticket (exit 1); running ticket (exit 1, file unchanged); judging twice and three times, which keeps earlier judgements oldest first; minutes missing, -1, 1441, x and 1.5 refused with exit 2; and the CLI printing a single line with 1440 accepted.

- met: The documentation the change affects is updated (C25).

  docs/reference/cli.md is regenerated with the `judge` subcommand, and the docs: references check passes. docs/architecture/modules/cli.md and docs/architecture/modules/shadow.md describe `judge`. The README's shadow section mentions `ariane judge 12 accept --minutes 20 --note ...` and `judgements_before`. The change adds no log calls, so the log catalogue is unaffected. One minor gap: the arrows in 3-components.md weren't extended (see findings).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0037-judge-command.md records the choices the spec left open: argparse refusing bad minutes with exit 2, earlier judgements appended oldest first, the `at` timestamp in UTC, editing the file in place without committing it in the clone, and storing the judgement in metrics.json rather than a separate file. Rejected alternatives are listed.

## Proposed learnings (not decided)

- When a module doc's collaboration diagram gains arrows, check that docs/architecture/3-components.md gains the same arrows; no check catches the drift today.
- Commands that read a JSON record written by Ariane should turn a JSONDecodeError into the one-line C23 message instead of a traceback.
- Data written into a shadow clone without a commit (like the judgement) can be lost if the file is rewritten or restored; the report ticket should treat the working-tree metrics.json as the source of truth.
