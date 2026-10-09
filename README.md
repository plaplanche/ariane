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

PowerShell:

```powershell
uv tool install git+https://github.com/plaplanche/ariane
$env:GH_TOKEN = "<a token with access to the repository>"
ariane start 12
ariane status 12
```

bash:

```bash
uv tool install git+https://github.com/plaplanche/ariane
export GH_TOKEN="<a token with access to the repository>"
ariane start 12
ariane status 12
```

For a project other than Ariane, start from [`docs/ariane.example.toml`](docs/ariane.example.toml):
copy it to `ariane.toml` at the root of your repository and adapt it.

`ariane start` creates the branch `ariane/12` in a working tree beside the repository
(`<repo>.ariane/worktrees/12`), runs the setup command, one implementer session, every check,
then pushes the branch, opens the pull request and publishes each check's result as a commit
status (`ariane/<check name>`) on its head commit. The ticket's records are in `work/12/`.
A GitHub Actions workflow (`check-statuses.yml`) also publishes these statuses from the committed
report, including when Ariane cannot (for example from a cloud session).
The token needs permission to write commit statuses (for a fine-grained token, "Commit statuses:
read and write"), on top of reading issues and writing pull requests.

- [`docs/spec.md`](docs/spec.md): vision, functional specification (capabilities C1 to C24),
  non-functional requirements, roadmap and founding decisions.
- [`docs/adr/`](docs/adr/): architecture decision records, written as the implementation goes.

## While a ticket runs

Nobody runs git commands in the repository or pushes to it while a ticket runs. Ariane checks
that the agent changed nothing outside the ticket branch (git configuration, hooks, local
branches, the remote); it cannot tell a person from the agent, so any such change stops the
ticket (ADR 0017). Wait for the ticket to finish, or start it again after a stop.

## License

Ariane is free software under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`): you may use, study, modify and share it, and anyone who offers a modified
Ariane to others, including as a network service, must publish their changes under the same
license. Other licensing terms can be arranged with the copyright holder
([ADR 0008](docs/adr/0008-license.md), [ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
Fixes are sent as issues.
