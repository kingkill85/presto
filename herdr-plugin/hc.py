"""herdr-core (`hc`, the terminals behind the Herdr desktop app) as the source
of agents and spaces, instead of the Herdr TUI and its plugin hooks.

`hc events --json` prints a snapshot of all terminals as its first line, then
one line per change (status, title, created, finished, ...). `snapshot()` reads
just that first line; `Watcher` follows the stream and sets an event on every
change, so the agent status goes out right away.
"""

import json
import shutil
import subprocess
import threading
import time

STATUS = {"error": "blocked"}  # hc: idle, working, done, blocked, error
KIND = {"claude-code": "claude"}


def available():
    """True while an hc core answers on this computer."""
    if not shutil.which("hc"):
        return False
    try:
        return subprocess.run(["hc", "server", "status"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def snapshot():
    """All terminals, as the first line of the event stream (it has titles and
    labels, `hc ls` doesn't)."""
    proc = subprocess.Popen(["hc", "events", "--json"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    try:
        timer = threading.Timer(10, proc.kill)
        timer.start()
        line = proc.stdout.readline()
        timer.cancel()
    finally:
        proc.kill()
        proc.wait()
    if not line:
        raise RuntimeError("hc events gave no snapshot")
    return json.loads(line)["terminals"]


def _number(term):
    try:
        return int("".join(c for c in term["address"] if c.isdigit()) or 0)
    except (KeyError, ValueError):
        return 0


def space(term):
    """Space name: the part before " / " in the `where` label ("presto / 1")."""
    where = (term.get("labels") or {}).get("where") or ""
    return where.split(" / ")[0].strip() or term.get("address", "")


def live(terms):
    return sorted((t for t in terms if t.get("state") == "live"), key=_number)


def agents(terms):
    """Live terminals running an agent, like `herdr agent list`:
    [{"workspace", "agent", "title", "status"}]"""
    out = []
    for t in live(terms):
        status = t.get("status") or {}
        if not status.get("state"):
            continue  # a plain shell
        app = status.get("app") or ""
        out.append({
            "workspace": space(t),
            "agent": KIND.get(app, app),
            "title": t.get("title") or "",
            "status": STATUS.get(status["state"], status["state"]),
        })
    return out


def spaces(terms):
    """[(space, cwd)] of every live terminal, in terminal order."""
    return [(space(t), (t.get("foreground") or {}).get("cwd") or t.get("cwd")) for t in live(terms)]


class Watcher(threading.Thread):
    """Follows `hc events` and sets `changed` on every change (not on the
    heartbeats). Restarts the stream when hc goes away and comes back."""

    def __init__(self):
        super().__init__(daemon=True)
        self.changed = threading.Event()

    def run(self):
        while True:
            try:
                proc = subprocess.Popen(["hc", "events", "--json"], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                for line in proc.stdout:
                    if b"heartbeat" not in line[:200]:
                        self.changed.set()
                proc.wait()
            except OSError:
                pass
            time.sleep(10)
