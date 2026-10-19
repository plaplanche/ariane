# Module `ariane.review_session`

The reviewer sessions of one review round (C10): a fresh read-only session on the reviewer tree (the commit without `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md` and `.claude/`, ADR 0031), and one new session if its answer is invalid.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `ReviewFailed` | exception | No valid answer; carries `reason`, `next_action` and `detail`. |
| `read_answer(result)` | function | The validated answer of a session result, or the reason it is not one. |
| `ReviewSession` | dataclass | What the reviewer sessions of a ticket share; `run` returns the validated `Review`; `changed_lines` is the size of the reviewed diff, `small` whether it is a small change and `reviewer` the settings its sessions use (ADR 0046). |
| `agent_logins(runtime, implementer, reviewer)` | function | The login variables of each kind of agent session: `implementer`, `reviewer` and `reviewer.small` (the small reviewer's model, or the reviewer's when the small table sets none), each from `runtime.login_for` (ADR 0046, ADR 0024). |
| `cap_text(agent)` | function | Words the caps that apply, for the journal. |
| `instruction_dirs(tree)` | function | The folders whose instruction files, with their ancestors', a reviewer on `tree` can load: the system temporary folder and the tree's parent (ADR 0031). |

## Behaviour and errors

- `ReviewSession`: what the reviewer sessions of a ticket share; `run` returns the validated answer and calls back to verify that the session changed nothing.
- A Claude Code reviewer runs from a temporary empty folder and reads the tree through `Session.add_dirs`; opencode, Codex and pi run in the tree. `instructions` is the base branch's `CLAUDE.md`, passed to the prompt as data.
- Before its sessions, `run` journals `ticket.review.instructions`: how many places `git.instruction_snapshot` checked for `instruction_dirs(tree)` and the reviewer's runtime, and the digest of each file present. The flow's guard holds the same snapshot from before the implementer's session, so a file written there by an agent, a check or a setup stops the ticket before the review (ADR 0031).
- Small change (C10, ADR 0046): the caller passes `changed_lines` (`git.changes(...).changed_lines` of the reviewed range, without `work/`). When `agent.small` (`[agents.reviewer.small]`) exists and the count is at most its `max_lines`, `small` is true and `reviewer` is the reviewer's settings with the small table's `model`, `max_budget_usd`, `max_tokens` and `timeout_minutes` where given (runtime and tools unchanged; an idle limit at or above the small time limit is dropped, since it could never fire first); the prompt gets `small_lines`. Otherwise `reviewer` is `agent` unchanged. The `ticket.review.started` entry names the model used and ends with "small change (N changed lines, at most M): small reviewer settings" or "N changed lines"; a cap stop in a small round names `agents.reviewer.small.<key>` when the small table set that cap. The callers record `reviewer.model` in `review-<round>.md`.
- `run` takes `name_status` (the untruncated changed-file list) and passes it to `review.prompt`.
- Its `env` is built by the caller from the login variables of the reviewer's model only, and `small_env` from those of the small reviewer's model (`agent_logins`); a small round's sessions get `small_env` when given, so a small model on another opencode provider gets its own key and never the reviewer's (ADR 0046).
- The journal line of a reviewer session starts with the reviewer's runtime as `runtime.describe` words it (for opencode: its version and that the title call's usage is not reported).
- `cap_text` words the caps that apply for the journal: for opencode "runtime cost cap none; Ariane stops at … USD of reported cost or … tokens".
- A reviewer session stopped at a cap: the `ticket.review.stopped` entry starts with "Cap reached: <cap>."; `ReviewFailed` says "the reviewer session stopped at <cap>" and its next action names `agents.reviewer.max_tokens` or `agents.reviewer.max_budget_usd` (#139). Other stop reasons keep "the reviewer session stopped: <reason>"; a `timeout` adds its summary in parentheses (`SessionResult.stop_text`), and its `ticket.review.stopped` entry starts with that summary, which says whether the total or the idle limit was reached (ADR 0045).
- A `quota` stop ends the ticket with "reviewer quota reached" and the result's next step ("restart the ticket after <time>"), never a no-go; a result with a `next_step` (Codex not logged in) stops with its summary and that step (ADR 0043). `cap_text` for Codex says the cost is billed by the plan or the API key; for pi, "runtime cost cap none (billed per token); Ariane stops at … USD of reported cost or … tokens". A pi session without credentials stops the same way, with "pi has no credentials for <provider>" and its login step (ADR 0051).
- Each reviewer session is run through `Metrics.run_session` when `metrics` is given (C19), with its review `round` and `changed_lines`.
- `read_answer`: the validated answer of a session result, or the reason it is not one.
- `ReviewFailed`: no valid answer (the session did not finish, or two invalid answers); the flow turns it into a stop with status `needs a human`.

## Workflow

```mermaid
flowchart TD
  A[ReviewSession.run replay, checked, diff, results, ...] --> B[temporary empty folder]
  B --> C[build the prompt with review.prompt]
  C --> D[run the reviewer session]
  D --> E[after_session: verify nothing changed]
  E --> F[read_answer]
  F -- valid --> G[return Review]
  F -- invalid, first time --> H[one new session with the error] --> E
  F -- unfinished or invalid twice --> X[raise ReviewFailed]
```

## Code view (C4 level 4)

```mermaid
classDiagram
class ReviewSession {
  <<dataclass>>
  runtime AgentRuntime
  agent AgentConfig
  folder TicketFolder
  issue Issue
  env Mapping
  all_checks Sequence
  definition_of_done Sequence
  instructions str
  metrics Metrics
  round int
  changed_lines int
  small_env Mapping
  small bool
  reviewer AgentConfig
  run(replay, checked, diff, results, not_updated, after_session) Review
}
class ReviewFailed {
  <<exception>>
  reason str
  next_action str
  detail str
}
ReviewSession ..> ReviewFailed
ReviewSession ..> Review
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  flow --> review_session
  replay --> review_session
  review_session --> checks
  review_session --> config
  review_session --> git
  review_session --> metrics
  review_session --> review
  review_session --> runtime
  review_session --> ticket
  review_session --> tracker
  verify --> review_session
```
<!-- end generated -->

## Serves

C10; ADR 0016, ADR 0025, ADR 0027. See [the component view](../3-components.md).
