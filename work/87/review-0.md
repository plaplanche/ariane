# Review 0

- Reviewed commit: `3bebcab44785adb8b3ebbaf07587cadfebc344df`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/context.py:98`) known_secrets docstring is now inaccurate

  The docstring says known_secrets returns "the value of every variable `untrusted_environment` withholds". untrusted_environment now also withholds ARIANE_CONFIG, and known_secrets deliberately ignores it, as the ticket decided. The docstring should name that exception.

- **minor** (`tests/test_context.py:80`) Second acceptance criterion is only covered at unit level

  No test starts a run (`ariane start` or `ariane verify`) with ARIANE_CONFIG set and checks that the checks' environment lacks it. The unit test with login_variables=() matches what flow.py:151 and verify.py:119 build for the checks, and those environments are what checks.run_checks receives (flow.py:494, verify.py:177). So the 'equivalently' wording of the criterion is arguably met. Still, nothing guards against a future call site that builds the checks' environment another way.

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

  test_c22_untrusted_environment_drops_ariane_config_in_any_case (tests/test_context.py:80) passes ARIANE_CONFIG and ariane_config, both with and without a login variable. It asserts both are dropped while KEEP_ME is kept, and that known_secrets stays empty. Without the new branch at context.py:132, ARIANE_CONFIG would be copied through and the assertion would fail. It matches the `-k c22_untrusted_environment` checklist item.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/context.md now lists ARIANE_CONFIG among the variables untrusted_environment withholds: matched case-insensitively, not a secret. README's ARIANE_CONFIG paragraph says it does not reach the agents or the checks. The untrusted_environment docstring is updated too. The known_secrets docstring was not (minor).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's 'Decided spec' fixes the behaviour: drop ARIANE_CONFIG case-insensitively for both agents and checks, and leave known_secrets unchanged. The change leaves no design choice open, so no ADR is needed.

## Proposed learnings (not decided)

- When untrusted_environment withholds a new non-secret variable, check whether known_secrets' docstring ('every variable untrusted_environment withholds') still holds.
- A unit test of untrusted_environment with login_variables=() stands for the checks' environment only as long as flow.py and verify.py build it that way. An end-to-end check would guard the call sites.
