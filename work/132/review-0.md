# Review 0

- Reviewed commit: `c33244b8fa39b70703579db2a1190d85e96a4281`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/context.py:100`) known_secrets docstring is now even less accurate

  The docstring still says known_secrets returns 'the value of every variable `untrusted_environment` withholds'. untrusted_environment now also withholds every ARIANE_* variable, VIRTUAL_ENV, VIRTUAL_ENV_PROMPT and some PATH entries, and known_secrets deliberately ignores them. The review of #87 already flagged this and kept it as a learning. The docstring should name the exception, for example: 'withholds as a credential'.

- **minor** (`docs/architecture/modules/context.md:17`) 'known_secrets ignores them' is imprecise for secret-looking ARIANE_* names

  The text says the ARIANE_*/virtual-environment variables are not secrets, so known_secrets ignores them. An ARIANE_* variable whose name looks like a credential (for example ARIANE_API_KEY) still matches _SECRET_NAME, so known_secrets does return its value. It would be better to say that known_secrets ignores them unless the name looks like a credential.

- **minor** (`docs/architecture/modules/context.md:27`) Workflow diagram has a dangling node

  The new node B2 ('remove Ariane's scripts directory from PATH') branches off B and leads nowhere, while C continues to D. In the code, the PATH filtering happens inside the same loop, before the login-variable step. Merging it into C, or linking B2 --> D, would show the flow correctly.

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

  tests/test_context.py adds 4 tests named test_c9_own_environment_*. They cover withholding from the checks, an unchanged PATH, an agent session with login_variables ('ARIANE_' prefix declared and still withheld), and case-insensitive names with normalised entries (trailing separator, 'Path'). Paths are built with os.path.join/os.pathsep. Without the change, VIRTUAL_ENV, ARIANE_LOG_LEVEL and the scripts entry would pass, so the assertions would fail. tests/test_flow.py::test_c9_own_environment_does_not_reach_the_checks runs flow.start with the fake runtime and VIRTUAL_ENV/ARIANE_LOG_LEVEL in environ, with a check that exits nonzero if either is present. flow.py:156-158 builds the check environment through untrusted_environment, so before the change that check would fail and exit_code would be nonzero. In total `-k c9_own_environment` selects 5 tests.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/context.md is updated in both sections the ticket names: 'Behaviour and errors' and the workflow diagram. The README's 'While a ticket runs' section gets a one-sentence statement. No public symbol or log event changed, so the generated references and docs/logs.md need no regeneration, and the docs-references check passes. Minor imprecisions are noted in the findings.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0040-own-environment-is-not-the-projects.md uses the next free number after 0039. It records the rule, why the whole ARIANE_ prefix is withheld rather than a list, the normalisation, the out-of-scope variables and the alternative considered. The ticket's decided spec fixes the remaining behaviour.

## Proposed learnings (not decided)

- When untrusted_environment withholds a new non-secret variable, update known_secrets' docstring ('every variable untrusted_environment withholds') in the same change. This has been missed twice (#87, #132).
- Mermaid workflow edits in docs/architecture/modules/*.md should keep each new node connected to the main flow; a node branching off and ending nowhere misdescribes the order of steps.
- Environment filtering that depends on sys.prefix != sys.base_prefix also applies when the test suite itself runs under `uv run`. End-to-end tests should call checks through sys.executable (absolute), not through a bare command that resolves via PATH.
