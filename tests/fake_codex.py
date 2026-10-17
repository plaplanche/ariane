"""A stand-in for the `codex` executable: prints a recorded JSON Lines stream.

Usage: fake_codex.py <events.jsonl> <dump.json> <exit code> <hang|end>
<in|apikey|out|crash> <codex arguments>
"""

import json
import os
import sys
import time

events, dump, code, end, login = sys.argv[1:6]
args = sys.argv[6:]
if args == ["--version"]:
    print("codex-cli 0.163.0")
    sys.exit(0)
if args == ["login", "status"]:
    print(
        {
            "in": "Logged in using ChatGPT",
            "apikey": "Logged in using an API key - sk-...",
            "crash": "boom",
        }.get(login, "Not logged in")
    )
    sys.exit(0 if login in ("in", "apikey") else 1)
stdin = sys.stdin.read()
with open(dump, "w", encoding="utf-8") as out:
    json.dump({"argv": args, "env": dict(os.environ), "stdin": stdin, "cwd": os.getcwd()}, out)
with open(events, encoding="utf-8") as lines:
    for line in lines:
        print(line.rstrip("\n"), flush=True)
if end == "hang":
    time.sleep(60)
sys.exit(int(code))
