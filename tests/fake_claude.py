"""A stand-in for the `claude` executable: prints a recorded result, sleeps, or echoes its input.

Usage: fake_claude.py <mode> [fixture] -- <the flags Ariane passes>
"""

import json
import os
import sys
import time

mode = sys.argv[1]
prompt = sys.stdin.read()
if mode == "fixture":
    with open(sys.argv[2], encoding="utf-8") as fixture:
        print(fixture.read())
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
