# Review 0

- Reviewed commit: `672c343dc1b61cb3a8ecdd68dd728e9acfc010c9`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/git.py:222`) Scope filter contradicts the decided spec ("in any scope")

  The ticket's decided spec says `push_rewrites(cwd, url)` returns the matching `url.<base>.insteadof` / `pushinsteadof` settings "in any scope". The code still keeps only `scope in ("local", "worktree", "command")`, so the guard ignores a global or system `url.<evil>.pushInsteadOf=https://github.com/` and lets it reroute the push. That is the one thing the narrowed guard is now meant to catch, and the config snapshot does not cover global scope either. ADR 0017's amendment (docs/adr/0017-push-guard-revision.md:101-102) records the narrower 'local, worktree or command' scope without giving a reason. No test covers a global or system key. Fix: either drop the scope filter, since a key that matches the push URL is now precise enough to stop on in any scope, or ask the owner and record the decision with its reason.

- **minor** (`src/ariane/git.py:218`) Parsing on the first '=' misses rewrites whose base contains '='

  `setting.partition("=")` splits `url.https://evil/?a=b.pushinsteadof=https://github.com/` into the key `url.https://evil/?a`. That key does not end with `.pushinsteadof`, so the rewrite is never seen and the explicit check is bypassed. This bug was already there before this change, and the snapshot guard still catches a local key added during the run. Since the parsing is being touched anyway, use `git config --null --list --show-scope`, or `--get-regexp` on the variable name, to split the key from the value reliably.

- **minor** (`src/ariane/git.py:214`) Rewrites are read from a different environment than the one the push uses

  `push_rewrites` runs git with `token_free_environment()` built from `os.environ`, while `git.push` builds its environment from `Delivery.environ`. Today both come from the same `os.environ` copy (cli `_environment_with`), so their `GIT_CONFIG_*` variables match. But the guard should inspect the environment the push actually uses: pass `self.environ` (filtered) so that a future caller cannot make them diverge.

- **minor** (`tests/test_c11_push_rewrite.py:74`) Matching-key tests rewrite the URL to itself rather than to <other>

  The acceptance criteria name `url.<other>.pushinsteadof` and `url.<other>.insteadof` with a prefix that matches the push URL. Both tests use `url.{remote}.…={remote}`, so the base equals the prefix and the rewrite changes nothing. The guard still stops, so the behaviour is shown, but a base such as `https://elsewhere.invalid/` would match the scenario the issue describes. No test shows a local key with a prefix that does not match being ignored. The environment-injected test only covers command scope.

- **blocking** Definition of done not met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0017 amendment records the push-URL matching rule. It also states a scope restriction (local, worktree, command) that the decided spec did not leave open: the spec says 'in any scope'. The restriction comes with no reason and no owner decision.

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

  tests/test_c11_push_rewrite.py: `..._environment_ssh_to_https_does_not_apply` calls the new two-argument signature (a TypeError on the base code), and `..._environment_keys_do_not_stop_the_delivery` would hit 'rewrites URLs' on the base code. The two matching-key tests are regression tests. Four tests match `-k c11_push_rewrite`. Nothing tests the global or system scope that the spec includes.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/git.md (table, notes, class diagram) and docs/architecture/modules/delivery.md (last guard) are updated, and ADR 0017 has the amendment. They describe the local/worktree/command scope restriction, which itself departs from the decided spec (see the blocking finding).

- **not met**: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0017 amendment records the push-URL matching rule. It also states a scope restriction (local, worktree, command) that the decided spec did not leave open: the spec says 'in any scope'. The restriction comes with no reason and no owner decision.

## Proposed learnings (not decided)

- When a ticket narrows a security guard, check every qualifier in the decided spec (here 'in any scope') against the old filters the code keeps; leftover filters quietly weaken the guard.
- Parse `git config --list` with `--null` (or `--get-regexp`): url.<base> subsections can contain '=' and break `partition('=')`.
- A guard that inspects git configuration should run with the same environment (`GIT_CONFIG_*`) as the command it guards.
