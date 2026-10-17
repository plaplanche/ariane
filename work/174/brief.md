# Product brief: Push guard: stop only on URL rewrites that apply to the push URL (C11)

- Source: issue #174 (https://github.com/plaplanche/ariane/issues/174)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The last guard before the push (#172, ADR 0017) stops the delivery when git configuration holds any `url.*.insteadof` or `url.*.pushinsteadof` key in the local, worktree or command scope. In a cloud container, the environment injects command-scope keys through `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` that rewrite `git@github.com:` and `ssh://***@github.com/` to `https://github.com/`. The remote is already `https://github.com/...`, so these keys never apply to the push, yet ticket #160 stopped at delivery after its checks and review had passed:

```
Stopped ticket #160: git configuration rewrites URLs, which could reroute the push (url.https://github.com/.insteadof=git@github.com:; url.https://github.com/.insteadof=ssh://***@github.com/). Next: remove the url.*.insteadOf keys; Ariane pushed nothing.
```

Spec: C11 (delivery), ADR 0017 (push guard).

## Current state

- `src/ariane/git.py:208-218` `push_rewrites` lists every rewrite key in the local, worktree and command scopes, whatever URL it applies to.
- `src/ariane/delivery.py:99-108` `_last_guard` stops on any of them.

## Decided spec

- **A rewrite stops the push only if it applies to the push URL.** `push_rewrites(cwd, url)` takes the URL Ariane pushes to and returns the `url.<base>.insteadof=<prefix>` and `url.<base>.pushinsteadof=<prefix>` settings, in any scope, whose `<prefix>` is a prefix of that URL (git's own matching rule). Keys whose prefix does not match the push URL are ignored.
- `_last_guard` passes the push URL it is about to use. The message and the `Next:` line stay as they are.
- ADR 0017 amendment: the guard is about the push URL, not about every rewrite key, and why (environment-injected rewrites in cloud containers).

## Release note

Fixed: the last guard before the push no longer stops on URL rewrites that do not apply to the push URL, such as the SSH-to-HTTPS rewrites a cloud environment injects.

## Acceptance criteria

- Tests named `test_c11_push_rewrite_*` show:
  - command-scope rewrites from `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` of `git@github.com:` to `https://github.com/`, with an `https://` remote, do not stop the delivery;
  - a local `url.<other>.pushinsteadof` whose prefix matches the push URL still stops the delivery before the push;
  - a local `url.<other>.insteadof` whose prefix matches the push URL still stops it.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c11_push_rewrite` runs at least 3 tests and they pass.
- [ ] ADR 0017 has the amendment.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/git.md`, `delivery.md`.

## Related

ADR 0017; spec C11; #172.
