# Review 1

- Reviewed commit: `2b3392a9682ad0fc818e634bc535b83b7d927449`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_c11_push_rewrite.py:88`) The insteadOf acceptance test uses an identity rewrite instead of `url.<other>`

  The acceptance criterion asks for "a local `url.<other>.insteadof` whose prefix matches the push URL". The test sets `url.{remote}.insteadOf = {remote}`, which rewrites the remote URL to itself, so the base is not "other". The same change was made in test_c11_guard_hardening.py:119. The guard still stops on it, because the match is on the value and not the base, so the behaviour is covered. A base like `https://elsewhere.invalid/` would match the ticket's wording and show a real reroute.

- **minor** (`docs/adr/0017-push-guard-revision.md:97`) ADR body still says "any local key stops it" above the amendment

  Line 97 still reads "any local `url.*.insteadof` or `url.*.pushinsteadof` key stops it". The amendment below it overrides this, and that is acceptable for an amendment. A short "(amended below)" marker would stop readers from taking the old rule as current. Line 102 of the amendment is also much longer than the wrapping used in the rest of the file.

- **minor** (`src/ariane/git.py:214`) The guard reads the config with a slightly different environment than the push

  `push_rewrites` reads the config with `token_free_environment(env)`. `push` runs with `push_env(environ)`, which keeps the credential variables and adds `credential.helper` and `http.extraHeader`. None of the filtered variable names (TOKEN/SECRET/… and the askpass/ssh sockets) change which config files git reads or the `GIT_CONFIG_*` keys, so in practice both see the same `url.*` settings. I am noting the difference so later changes to the filter do not open a gap. Order of writes on the delivery path: set_status, then commit_record, then _require_replayed, then guard(), then push_rewrites (read-only), then git.push. The guard is still checked right before the only external write (the push), and no agent runs between the check and the push, so nothing can change the config in between. The status write ("pushed") and the local record commit come before the guard, but that order predates this change, and a stop overwrites the status.

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

  tests/test_c11_push_rewrite.py adds 7 `test_c11_push_rewrite_*` tests. Without the change, `test_..._environment_ssh_to_https_does_not_apply` and `test_..._environment_keys_do_not_stop_the_delivery` would fail: the old code stopped on every command-scope key and took no URL argument. `test_..._global_key_applies` would also fail, because the old code ignored the global scope. The matching pushInsteadOf and insteadOf tests show the guard still stops before the push (pushes == [], and snapshot_changes is blinded so only the explicit check can see the key). The test run that Ariane replayed passed.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/git.md (table row, prose and class diagram) and docs/architecture/modules/delivery.md (last-guard bullet) now describe the push-URL matching. ADR 0017 has the amendment. No logs, CLI or schema changed, so nothing generated needs regenerating.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the design (prefix match, any scope, unchanged message). The remaining choices are recorded in the ADR 0017 amendment: covering every scope including global and system, and reading the config from the push's environment.

## Proposed learnings (not decided)

- When a guard checks git configuration that affects a later git command, read it with the same environment that command will use, because command-scope keys (GIT_CONFIG_COUNT/KEY_n) and GIT_CONFIG_GLOBAL live in that environment.
- Parse `git config --list` with `--null` and split each entry on the first newline: url.<base> subsections can contain '=', so splitting on '=' gets the key wrong.
- Fixtures for 'a matching rewrite still stops' should rewrite to a different base, not to the URL itself, so the test shows a real reroute.
