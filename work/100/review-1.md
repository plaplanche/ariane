# Review 1

- Reviewed commit: `433f7ba119668b0c10ca9c5639f117d3fa093245`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`README.md:146`) Token permission may be understated for organisation repositories

  The prerequisites ask only for 'a GitHub token with read access to the project's issues'. However, the label gate (src/ariane/github.py:115-136) also calls GET /repos/{repo} and, unless the labeller owns a user-owned repository, GET /repos/{repo}/collaborators/{user}/permission. Any error other than a 404 from that endpoint becomes IssueRefused. On an organisation repository, a token limited to issue read access may be refused there, and the second user's first ticket would exit 2. It would be worth stating the needed scope, for example 'read access to issues and repository metadata/collaborators', or checking it against a fine-grained token.

- **minor** (`README.md:159`) Command blocks do not say where to run them

  The bash and PowerShell blocks download ariane.toml into the current directory and run `git fetch origin` and `ariane start`. Ariane resolves the repository from the current directory, but neither block says 'from the root of your repository'. Step 2 implies it, but a first-time user who runs `uv tool install` from elsewhere could carry on in the wrong directory.

- **minor** (`README.md:154`) Restarting a shadow ticket is not mentioned in the new section

  `ariane start --shadow <n>` stops if `<repo>.ariane/shadow/<n>` already exists (src/ariane/shadow.py:70-71). The earlier README paragraph says 'Remove the clone to start the ticket over', but the self-contained second-user path leaves this out. The second user is likely to hit it after an interrupted run.

- **minor** (`tests/test_docs_readme_shadow.py:38`) Unexplained negative assertion

  `assert "cp docs/" not in section()` encodes the decision that the second user has no local copy of Ariane's docs/ and must download the example. It has no comment, so a later reader may find it puzzling. A short docstring would match the intent.

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

  tests/test_docs_readme_shadow.py adds three tests named test_c19_readme_shadow_*. Without the README change, section() fails on `assert HEADING in text`, so all three fail. They check for the section, the 'never pushes' and '10 tickets' statements, and `--shadow`, `ariane judge` and `ariane report` in both the ```bash and ```powershell blocks, as the acceptance criteria ask. Ariane's replayed test check passed.

- met: The documentation the change affects is updated (C25).

  README.md has the new section 'Measure Ariane on your project (shadow mode)' and an updated status line saying slice 4 is built and its gate is pending. The README's claims match the code: clone path (shadow.clone_path), judge syntax with --minutes 0..1440 (cli.py), the `shadow pass: yes|no` line (measures.py:127), report reading the shadow clones (report.py:23-30), and the tracker.ready_label default `ariane` (config.py:34). No code changed, so docs/architecture, the generated references and the log catalogue are unaffected. The docs: references check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The change is documentation only, and the ticket's 'Decided spec' fixes its content: section name, prerequisites, ADR 0021 installation, commands, pass criteria and the status line. The only new detail is how to get the example (curl or Invoke-WebRequest from the raw GitHub URL). That follows from ADR 0021, where installation is through uv tool from git and leaves no local docs/, so no new ADR was needed.

## Proposed learnings (not decided)

- Documentation-only tickets should still check README claims against the code (paths, flags, output lines). Here they matched shadow.py, cli.py, measures.py and report.py.
- Token-permission statements in user-facing docs should be derived from every API endpoint the code calls, for example the label gate's collaborator-permission check, not only from the obvious one.
