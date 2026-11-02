#!/usr/bin/env python3
"""Claude's usage limits (5 hour window and week) for the Presto.

Claude Code hands its status line script the limits as `rate_limits`; the
status line saves them with a time stamp (see the README):

  {"five_hour": {"used_percentage": 70, "resets_at": 1793642400},
   "seven_day": {"used_percentage": 7, "resets_at": 1794236400}, "ts": 1793640998.1}

The poller (pipelines.py) reads that file every round and sends

  {"type": "usage", "src": "myhost", "ts": 1793640998,
   "5h": {"p": 70, "r": "18:00"}, "7d": {"p": 7, "r": "Mo 9:00"}}

The reset time is local time from this computer, so the Presto needs no
time zone maths; the 5 hour window only gets the time (it is never further
away than that), the week the day too. A window that has reset since the
file was written counts as 0 % (nobody used Claude since, or the file would
be newer).

  python3 usage.py        # print the message
"""

import json
import os
import time

FILE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "presto-usage.json")
MAX_AGE = 8 * 86400  # older than a week: nothing to say any more
DAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def window(limit, now, with_day):
    if not limit or limit.get("used_percentage") is None:
        return None
    reset = limit.get("resets_at")
    if reset and reset <= now:
        return {"p": 0}
    out = {"p": round(limit["used_percentage"])}
    if reset:
        t = time.localtime(reset)
        out["r"] = (DAYS[t.tm_wday] + " %d:%02d" if with_day else "%d:%02d") % (t.tm_hour, t.tm_min)
    return out


def collect(source, now=None):
    """The message for the Presto, or None without (recent) data."""
    now = now or time.time()
    try:
        with open(FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    ts = data.get("ts") or os.path.getmtime(FILE)
    if now - ts > MAX_AGE:
        return None
    msg = {"type": "usage", "src": source, "ts": int(ts)}
    for key, name, with_day in (("five_hour", "5h", False), ("seven_day", "7d", True)):
        w = window(data.get(key), now, with_day)
        if w:
            msg[name] = w
    return msg if len(msg) > 3 else None


if __name__ == "__main__":
    import socket
    print(json.dumps(collect(socket.gethostname()[:16])))
