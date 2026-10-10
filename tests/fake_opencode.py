"""A stand-in for the `opencode` executable: prints a recorded event stream.

Usage: fake_opencode.py <events.jsonl> <dump.json> <exit code> <hang|end> <opencode arguments>
"""

import json
import os
import sys
import time

events, dump, code, end = sys.argv[1:5]
args = sys.argv[5:]
if args == ["--version"]:
    print("1.18.35")
    sys.exit(0)
with open(dump, "w", encoding="utf-8") as out:
    json.dump({"argv": args, "env": dict(os.environ), "cwd": os.getcwd()}, out)
with open(events, encoding="utf-8") as lines:
    for line in lines:
        print(line.rstrip("\n"), flush=True)
if end == "hang":
    time.sleep(60)
sys.exit(int(code))
