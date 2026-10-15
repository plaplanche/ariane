# Module `ariane.shadow`

`ariane start --shadow <issue>` (C19, C23, ADR 0036): the whole ticket flow in a separate clone, with no push, no pull request, no commit status and no comment.

## Main types and functions

- `start`: reads the issue, refuses an existing clone ("remove it to start over"), clones the user's repository with `git clone --local --no-checkout` into `<repo>.ariane/shadow/<n>/`, removes `origin`, checks out `ariane/<n>` at the user's last known `origin/<base branch>` and runs the flow. The user's `.git` is only read, and nothing is fetched.
- `ShadowRun`: the ticket run of [flow](flow.md) with metrics mode `shadow`, no remote check and a local delivery: the outcome (`delivered`, or `needs a human` when the review is still `no-go`) goes to the journal, `status.md` and `metrics.json`, committed in the clone. The final line is "Shadow ticket #<n> done (<outcome>, review <verdict>). Next: read <clone>/work/<n>/, then run ariane judge <n> accept|reject --minutes N."
- `judge`: `ariane judge <n> accept|reject --minutes N [--note TEXT]` (ADR 0037) writes `judgement` into the shadow ticket's `metrics.json` and keeps earlier ones in `judgements_before`; no clone or a `running` ticket gives one line and exit 1.
- `clone_path`: where a shadow ticket lives.

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  cli --> shadow
  report --> shadow
  shadow --> checks
  shadow --> config
  shadow --> flow
  shadow --> git
  shadow --> metrics
  shadow --> review
  shadow --> runtime
  shadow --> stop
  shadow --> ticket
  shadow --> tracker
```
<!-- end generated -->

## Serves

C19, C23; ADR 0030, ADR 0036, ADR 0037. See [the component view](../3-components.md).
