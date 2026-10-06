# Ariane

Ariane turns tickets into reviewed pull requests with AI coding agents, while the human keeps
deciding, understanding and approving. The name comes from Ariadne's thread (*le fil d'Ariane*):
you never lose the thread of your own code.

**Status:** slice 1 (walking skeleton): `ariane start <issue>` takes a GitHub issue to a pull
request whose checks Ariane replayed. Approvals, reviews and the rest of the roadmap come next.

## Try it

Requirements: Python 3.11 or later, [uv](https://docs.astral.sh/uv/), git, and Claude Code
(`claude`) logged in. From the repository to work on, with an `ariane.toml` at its root (see
[ADR 0003](docs/adr/0003-configuration-file.md) and Ariane's own [`ariane.toml`](ariane.toml)):

```powershell
uv tool install <path-to-the-ariane-checkout>
$env:GH_TOKEN = "<a token with access to the repository>"
ariane start 12
ariane status 12
```

`ariane start` creates the branch `ariane/12` in a working tree beside the repository
(`<repo>.ariane/worktrees/12`), runs the setup command, one implementer session, every check,
then pushes the branch and opens the pull request. The ticket's records are in `work/12/`.

- [`docs/spec.md`](docs/spec.md): vision, functional specification (capabilities C1 to C24),
  non-functional requirements, roadmap and founding decisions.
- [`docs/adr/`](docs/adr/): architecture decision records, written as the implementation goes.
