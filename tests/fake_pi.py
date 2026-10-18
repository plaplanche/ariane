"""A stand-in for the `pi` executable: prints a recorded JSON Lines stream.

Usage: fake_pi.py <events.jsonl> <dump.json> <end|hang|nokey|plant|tree> <pi arguments>
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

events, dump, mode = sys.argv[1:4]
args = sys.argv[4:]
if args == ["--version"]:
    print("0.73.1")
    sys.exit(0)
stdin = sys.stdin.read()
seen = {"argv": args, "env": dict(os.environ), "stdin": stdin, "cwd": os.getcwd()}
if mode == "tree":  # a child that only the process tree's kill reaches
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    seen["child"] = child.pid
with open(dump, "w", encoding="utf-8") as out:
    json.dump(seen, out)
print('{"type":"session","version":3,"id":"s1","timestamp":"t","cwd":"."}', flush=True)
if mode == "nokey":
    print("No API key found for anthropic.\n\nUse /login to log into a provider", file=sys.stderr)
    sys.exit(1)
if mode == "plant":  # the session rewrites pi's own settings
    home = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent")
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.json").write_text('{"defaultModel": "x"}\n', encoding="utf-8")
with open(events, encoding="utf-8") as lines:
    for line in lines:
        print(line.rstrip("\n"), flush=True)
if mode in ("hang", "tree"):
    time.sleep(60)
