# Review 0

- Reviewed commit: `b3a5cb5597b835670d7cc4eb3ea4bf3382a2ef2a`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/cli.py:185`) The token goes back into a copy of the environment handed to the whole run

  The decided spec says the token is kept 'only in the tracker and the push'. `_environment_with` puts it back into a dict that flow/verify keep as `self.environ` for the whole run. flow.py:482 then reads it back through `_token`, and `context.known_secrets` reads it too. I followed every consumer: the copy only reaches `untrusted_environment` (which filters it), `known_secrets` and `git.push`, so no non-push subprocess gets it. The ADR 0017 amendment records this deviation. Passing `token` explicitly to the run, as `delivery.token` already does, would match the spec more closely.

- **minor** (`tests/test_c21_token_scope.py:84`) The failing-prctl test never checks the warning

  `caplog` is requested but nothing is asserted. The test only shows that `make_undumpable` does not raise. It does not show that `process.undumpable_failed` is journaled at warning level, which the spec requires. Add an assertion on the record.

- **minor** (`tests/test_c21_token_scope.py:17`) The CLI test calls `_take_token` directly, not through a command

  Nothing shows that `start`, `verify --issue` and `report` actually go through `_take_token`, or that `main` calls `process.make_undumpable` before any token is read. I checked by reading the code that all three call sites were switched. A test that runs `main` with a stubbed flow and then asserts `token_env not in os.environ` would cover the wiring.

- **minor** (`tests/test_c21_token_scope.py:65`) The environment-block test is skipped as root and does not involve the CLI

  The test is skipped when euid is 0. A cloud sandbox usually runs as root, so there it does not run at all. When it does run, it checks `make_undumpable` in a bare child interpreter, not the token Ariane read. This fits the acceptance wording and the stated residual, and the other 4 tests still meet the 'at least 4 tests' item. Note that `os.environ` deletion does not scrub the original block that `/proc/<pid>/environ` shows, so prctl is the only real protection there.

- **minor** (`docs/adr/0017-push-guard-revision.md:77`) The ADR leaves out other credential paths that the token-free git environment also cuts off

  The amendment only says that fetches can no longer use an SSH agent. Two more consequences are missing. GIT_ASKPASS is withheld. And the token variable is also withheld, so a credential helper that reads it (for example `gh auth git-credential` reading GH_TOKEN) no longer authenticates Ariane's own fetch or ls-remote on a private HTTPS origin. This behaviour is what the spec asks for, but the residual should be documented.

- **minor** (`src/ariane/cli.py:21`) The module-level `_TOKENS` cache outlives a single command

  Once `_take_token` has cached a value, later calls in the same process ignore the environment. That is harmless for a one-shot CLI. It is a latent test-order dependency, though: an 'empty token' test that ran in-process after a token was cached would pass the wrong way. Today the empty-token test in test_cli.py runs in a subprocess.

- **minor** (`docs/architecture/modules/context.md:12`) context.md has no note that the credential filter now comes from `git`

  Ariane flagged this file. `context` already imported `git` (the generated collaborations graph shows `context --> git`) and its public API is unchanged, so the page is not wrong. A one-line note that `SECRET_NAME` and `CREDENTIAL_CHANNELS` are shared with `git.token_free_environment` would keep the two pages consistent. docs/architecture/modules/logs.md needs nothing: it points to the generated catalogue, and the new type is there.

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

  tests/test_c21_token_scope.py has 5 tests named test_c21_token_scope_*. `_take_token`, `token_free_environment`/the default env in `git.git` and `make_undumpable` do not exist on the base, and the recording stub of `process.run` would see the token in the env on the base (env=None). Four tests run as root and five otherwise. One weakness: the prctl-failure test asserts nothing about the warning (minor finding).

- met: The documentation the change affects is updated (C25).

  The checklist's cli.md, git.md and process.md are updated. The README has the fine-grained token paragraph with the residual (line 44). The ADR 0017 amendment is added, and docs/logs.md lists `process.undumpable_failed`, matching logs.py (the docs reference check passes). context.md and the logs module page are not affected in substance (minor note).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The amendment to docs/adr/0017-push-guard-revision.md records three open choices: the in-memory environment copy for the run, the shared credential filter (with the SSH-agent consequence) and journaling a prctl failure as a warning. The askpass and credential-helper consequences are not recorded (minor finding).

## Proposed learnings (not decided)

- Deleting a variable from os.environ does not scrub /proc/<pid>/environ, which shows the original exec block; on Linux only PR_SET_DUMPABLE (or root-owned /proc entries) protects it.
- Stripping secret-looking variables from git's environment also disables credential helpers that read them (e.g. gh's helper and GH_TOKEN) and askpass; ADRs should list these as consequences, not just the SSH agent.
- A test that requests caplog should assert on the expected record; otherwise 'journaled as a warning' is untested.
