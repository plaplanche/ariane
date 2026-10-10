# Review 0

- Reviewed commit: `00ebf87edefcf06562125061b17c107220b4f4ba`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/opencode.py:99`) Too long a prompt in argv crashes Ariane instead of ending the session with `error`

  The whole review prompt (issue, the diff up to review.MAX_DIFF_CHARS = 200,000 chars, and the appended JSON Schema) goes into one argv element. Windows CreateProcess caps the whole command line at 32,767 chars, and Linux caps a single argument at 128 KiB (MAX_ARG_STRLEN). Past either limit, subprocess.Popen in process._execute raises OSError (WinError 206 / E2BIG). OpenCodeRuntime.run only catches process.CommandNotFoundError, and neither review_session nor flow catches OSError, so `ariane start` / `ariane verify` die with a traceback instead of journaling a stopped reviewer session and setting the status to `needs a human`. On the owner's Windows machine, almost any real ticket's diff passes 32K chars (this ticket's diff does), so slice 3's gate would crash. The fix needs at least: catch OSError in run() and return SessionResult(StopReason.ERROR, ...) with a clear message, plus a test (for example a fake executable path that raises, or a check on the prompt length). Better still, check the argv length before starting, or pass the large context another way. ADR 0029 notes the limit but not the crash.

- **minor** (`src/ariane/runtime.py:76`) Union of login variables gives the implementer the reviewer vendor's key

  flow/verify build one untrusted environment from runtime.login_variables, now the RoutedRuntime union. So the Claude Code implementer session, which has Bash and reads untrusted issue text, also gets OPENAI_API_KEY (or every AWS_* variable for amazon-bedrock). The opencode reviewer likewise gets ANTHROPIC_*/CLAUDE_*. ADR 0029 records this, but it widens credential exposure. Filtering the environment per role would keep least privilege.

- **minor** (`src/ariane/process.py:135`) The full prompt is emitted in the process.started log line

  With the prompt now in argv, logs.emit('process.started', ' '.join(args)) writes the whole prompt (up to about 200 KB of untrusted issue and diff text) as one log line for every opencode session. Consider shortening or leaving out the message argument in the log.

- **minor** (`src/ariane/config.py:165`) Every OSError is reported as 'file not found'

  load() now catches OSError and always says 'file not found'. ARIANE_CONFIG pointing at a folder, or at a file it cannot read, gets a misleading message. Include the exception text or tell the cases apart.

- **minor** (`tests/test_c5_opencode.py:186`) Test names a variable `claude` that holds an OpenCodeRuntime

  In test_c5_opencode_roles_are_routed_to_their_runtime, the variable `claude` is an OpenCodeRuntime, which makes the test confusing to read.

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

  tests/test_c5_opencode.py (14 test_c5_opencode_* tests) reads both fixtures, which are verbatim, through the adapter. They cover the sums (1,000/3,000/240, 0.0075), finished, the no-go answer, the token cap, the cost cap, error, the inline permissions, --pure/OPENCODE_DISABLE_CLAUDE_CODE and the implementer refusal. tests/test_config.py adds 3 test_c22_config_path_* tests. Without the change these fail on import or on config. The OSError path above has no test.

- met: The documentation the change affects is updated (C25).

  Added modules/opencode.md and config_schema.md. cli, config, flow, runtime and review_session module docs are updated, levels 0 to 3 show opencode, the README has the opencode section in PowerShell and bash, the schema reference is regenerated (docs: references check green), and there is a new example toml.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0029-opencode-reviewer.md records the routed runtime, the union of login variables, steps=20, the schema appended to the message, the caps and ARIANE_CONFIG path resolution.

## Proposed learnings (not decided)

- A runtime that passes the prompt as a command-line argument must handle OSError from process start (E2BIG on Linux, WinError 206 on Windows) and turn it into a session `error`, not an exception.
- With one runtime per role, build the agent environment per role, so one vendor's key does not reach another role's session.
