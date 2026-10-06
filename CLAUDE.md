# Working on Ariane

Ariane is specified in [`docs/spec.md`](docs/spec.md). Read it before any work: it is the only
input for building Ariane, and these rules come on top of it.

## When `ARIANE_ROLE` is set

If the environment variable `ARIANE_ROLE` is set, you are an agent session started by Ariane
(for example `implementer`), not a session with the owner. Then only this section applies, with
rules 1, 9 and 10 below:

- Do the task in Ariane's prompt, in the working tree you were given, and nothing else.
- Do not write `GATES.md`, spawn subagents, load skills, post to GitHub, ask questions or wait
  for an answer: nobody reads this session live.
- Do not push, switch branches, rewrite history or open pull requests: Ariane commits, replays
  the checks below and delivers.
- Run the checks below before finishing, and leave `work/` untouched.

## Rules

1. **The spec is the only source.** Build only from `docs/spec.md`, the ADRs and this repository.
   Never read, copy or adapt code from another repository or project, even to "see how it was
   done". If something you need is not in the spec, ask the owner instead of looking elsewhere.
2. **Ask, don't guess.** An ambiguity that changes behaviour goes to the owner as a question. A
   choice the spec leaves open is taken as the simplest design that meets it and recorded as an
   ADR in `docs/adr/` (see its README for the template).
3. **Follow the roadmap order.** One slice at a time, in the order of the spec's roadmap; a slice
   is done when its gate is checked and shown. Slice 1 is built by hand, since Ariane does not
   exist yet; from slice 2 on, Ariane's own tickets go through Ariane.
4. **Use the `unlazy` skill for each slice.** Write `GATES.md` (the slice's gate and acceptance
   criteria as checkable items) before starting, and run `--reverify` before reporting done.
   `GATES.md` and `.unlazy/` are git-ignored; never commit them. If `unlazy` is missing, install it
   pinned (its scripts run code, so never track a moving branch):
   `git clone https://github.com/Leonxlnx/unlazy ~/.claude/skills/unlazy && git -C ~/.claude/skills/unlazy checkout 16671491f6679ad9378f52604d3bc2415b4120c7`
5. **Independent review on a different model.** Before reporting a slice done, spawn a review
   subagent with `model: "opus"` explicitly (never the inherited default), adversarial, read-only.
   A "GO" that lists a blocking finding is a NO-GO. One fix round, one more review; after a second
   NO-GO, stop and hand over to the owner.
6. **Checks before every commit.** The lint, type and test commands are chosen in slice 1 and
   written here, under "Checks", in the same commit. From then on they pass before every commit,
   and CI runs the same commands on Windows, macOS and Linux.
7. **Leave a trace.** Each commit says what it implements (capability numbers, slice) and, when it
   finishes a ticket, has a line `Closes #N`.
8. **Before posting an issue or a comment**, write it to a file and run gstack's redaction check:
   `~/.claude/skills/gstack/bin/gstack-redact --from-file <file> --repo-visibility private --self-email "$(git config user.email)" --json`
   — post only if it reports no HIGH or MEDIUM finding. If the tool is missing, reread by hand for
   secrets, tokens and e-mail addresses, and say so.
9. **Nothing outside the project.** Code, docs, tests, commits, tickets and comments talk about
   Ariane only: no third-party organisation, employer, colleague or other project of the owner.
10. **English everywhere** in the repository: code, docs, prompts, commits, tickets.

## The owner's machine

The owner works on **Windows, in PowerShell 5.1**. Any command they are to run is given in
PowerShell syntax: no `sed`/`grep`/`/tmp`; line continuation is a backtick; no `&&` (use `;` and
check `$LASTEXITCODE`); long output piped through `Select-Object -Last N`. Multi-line edits go
through a here-string piped to `python -`.

## Cloud sessions

- `claude` refuses `--permission-mode bypassPermissions` as root (the sandbox user) unless
  `IS_SANDBOX=1` is set: set it when Ariane starts agents in a cloud session.
- A push touching `.github/workflows/` is refused from a cloud session (no `workflow` scope).
  Push everything else, leave the workflow file uncommitted, and tell the owner to commit and
  push it from their machine.

## Skills

Each slice follows these steps, in order (rules 3 to 5):

1. **Decide first.** List the choices the slice needs, propose one option each as a draft ADR,
   ask the owner the open questions as multiple choice, then run `/plan-eng-review` on the plan
   and wait for the owner's answers.
2. **Gates, then build.** Write `GATES.md` with `unlazy` from the slice's gate and the minimal
   form of its capabilities, lint it, then implement.
3. **Review before done.** Run `/review` on the diff, then the independent review of rule 5
   (a read-only subagent with `model: "opus"`), then `unlazy` `--reverify` on `GATES.md`.
4. **Deliver.** Push the slice branch and open a pull request; the owner merges.

Forbidden skills: `/ship` and `/land-and-deploy` (and any skill that pushes to the main
branch, merges, publishes or deploys). Delivery is a pushed branch and a pull request, merged by
the owner (C11).

## Checks

Run from the repository root after `uv sync` (ADR 0004). All of them pass before every commit,
and CI runs the same list on Windows, macOS and Linux:

| Check | Command |
| --- | --- |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types | `uv run mypy` |
| Tests | `uv run pytest` |
| File length | `uv run python scripts/check_file_length.py` |

Ariane's own `ariane.toml` declares the same checks for its tickets.
