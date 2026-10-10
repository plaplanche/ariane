"""A stand-in for the `claude` executable: prints a recorded result, sleeps, or echoes its input.

Usage: fake_claude.py <mode> [fixture] -- <the flags Ariane passes>
"""

import json
import os
import subprocess
import sys
import time

mode = sys.argv[1]
prompt = sys.stdin.read()
if mode == "fixture":
    with open(sys.argv[2], encoding="utf-8") as fixture:
        print(fixture.read())
elif mode == "stream":
    # stream <jsonl> <pidfile|-> <hang|end>: print the events one by one, optionally with a
    # background child (its pid in the pidfile), then hang or end.
    if sys.argv[3] != "-":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(sys.argv[3], "w", encoding="utf-8") as pidfile:
            pidfile.write(str(child.pid))
    with open(sys.argv[2], encoding="utf-8") as events:
        for event in events:
            print(event.rstrip("\n"), flush=True)
    if sys.argv[4] == "hang":
        time.sleep(60)
elif mode == "sleep":
    time.sleep(60)
elif mode == "echo":
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": json.dumps(
                    {
                        "argv": sys.argv[3:],
                        "prompt": prompt,
                        "role": os.environ.get("ARIANE_ROLE"),
                        "token": os.environ.get("GH_TOKEN"),
                    }
                ),
            }
        )
    )
elif mode == "crash":
    print("Error: not logged in", file=sys.stderr)
    sys.exit(1)
