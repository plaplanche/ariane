# Working on Ariane

Ariane is specified in [`docs/spec.md`](docs/spec.md). Read it before any work: it is the only
input for building Ariane, and these rules come on top of it.

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

## Checks

To be filled in slice 1 (lint, types, tests, file-length limit).
