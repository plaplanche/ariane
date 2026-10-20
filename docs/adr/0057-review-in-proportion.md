# 0057. Review in proportion: accepted residuals, ticket scope, sensitive paths

- Status: accepted
- Date: 2026-10-20
- Capabilities: C10, C26

## Context
The reviewer (C10) judges a change against the ticket and the definition of done (C26), but
nothing told it what the owner had already decided. On recent tickets it raised as blocking the
cases the owner had accepted as residuals in an ADR (until the operating-system sandbox), and edge
cases outside the ticket's scope; each one cost a fix round or a hand takeover. In the other
direction, a change to the push guard or to a workflow file got the same review as a change to a
README, with nothing pointing the owner to it.

## Decision
- **The marker.** An ADR records a residual the owner accepted as a list item whose line starts
  with `- **Accepted residual.**`; its indented continuation lines belong to it. Each item is
  self-contained (it names what it is about and until when it holds), since the reviewer sees the
  item without the ADR around it. The residuals of ADRs 0017, 0031 and 0047 carry it.
- **Read at the base commit.** Ariane reads the items from `docs/adr/` at the base commit, never
  from the change: a residual line the change adds is not listed. `ariane start` (and a shadow
  run) reads the files of the ticket's working tree right after it is created at the base, before
  any setup or agent session, so no git process is added to a run (ADR 0053); `ariane verify`
  reads them at the merge base with `git grep -l` and `git show`. The prompt lists them, `- ADR NNNN: <text>`, in an escaped untrusted block
  (`kind="accepted-residuals"`), and the rules say that a finding that is one of them is `minor`,
  with "accepted residual (ADR NNNN)" in its title.
- **Proportion.** The reviewer's rules always add: a case that neither the ticket nor the
  specification asks for, and that no acceptance criterion covers, is `minor`, unless it loses
  data, breaks a security property or makes a check pass wrongly; then it stays blocking and its
  detail says which of the three.
- **Sensitive paths.** An optional `[review] sensitive_paths` (path globs, the rules of
  `checks[].paths`). When the reviewed change touches one, the prompt says so and lists those
  files as data; when the delivered change touches one, the pull request gets the label
  `owner-review` and its body says, above the review, which sensitive paths changed. The label is
  added after the pull request opens (GitHub creates it if the repository lacks it); a refusal is
  the journaled warning `ticket.warning.label_refused` and the delivery goes on, since the body
  already names the paths. Ariane's own `ariane.toml` lists the push guard (`git.py`,
  `claude_code.py`, `delivery.py`), the run registry (`runs.py`), redaction (`redact.py`), process
  handling (`process.py`) and `.github/**`.
- These rules are framed opinions given to the reviewer, as the out-of-scope rule: `settle` is
  unchanged, a blocking finding still makes the verdict `no-go`, and nothing is merged or approved
  automatically.

## Consequences
- Fewer fix rounds and hand takeovers on findings the owner already decided or that no criterion
  asks for; a blocking finding outside the scope must name the data loss, the security property
  or the check it breaks.
- A residual is visible to the reviewer only once it is merged with the marker: accepting a new
  one is an owner decision recorded in an ADR, never something a change can grant itself.
- The reviewer can still be wrong about whether a finding is one of the residuals; a residual
  item that is too broad lowers the review. The items are kept narrow and dated by their ADR.
- A pull request touching a sensitive path is visible as such in the list of pull requests.

## Alternatives considered
- **Give the reviewer every ADR.** Too long for the prompt and buries the few decisions that
  matter; the marker makes the owner's acceptance explicit.
- **Read the residuals from the reviewed commit.** A change could then accept its own residual.
- **Turn residual or out-of-scope findings to minor in `settle`.** Ariane cannot tell from a
  title alone whether a finding is one of them; the reviewer's framing, with the title convention,
  keeps the decision visible in the record.
- **Stop or draft a pull request touching a sensitive path.** The owner merges every pull request
  anyway (C11); a label and a line are enough to direct their attention.
- **Fail the delivery when the label is refused.** The branch is already pushed and the body names
  the paths; a warning is enough.
