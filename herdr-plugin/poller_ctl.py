#!/usr/bin/env python3
"""Start, stop and keep alive the GitLab pipeline poller (pipelines.py).

Herdr has no supervised plugin daemons, so this follows the pattern other
GitLab plugins use: the startup hook and a few event hooks call `ensure`,
which starts the poller in the background unless it is already running. The
poller exits by itself when the Herdr server goes away.

  python3 poller_ctl.py ensure|start|stop|restart|status

State (pidfile, log) lives in $HERDR_PLUGIN_STATE_DIR. Settings are read from
pipelines.json in $HERDR_PLUGIN_CONFIG_DIR, for example:

  {"interval": 30, "target": "255.255.255.255", "enabled": true,
   "pinned": [{"host": "gitlab.example.com", "project": "group/project",
               "ref": "develop"}],
   "daynotes": "05-tagebuch"}

"daynotes" is optional (see daynote.py): a folder inside the Obsidian vault,
an absolute path, or "off".
"""

import json
import os
import signal
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(HERE, ".state")
CONFIG = os.environ.get("HERDR_PLUGIN_CONFIG_DIR") or HERE
PIDFILE = os.path.join(STATE, "pipelines.pid")
LOGFILE = os.path.join(STATE, "pipelines.log")
STOPPED = os.path.join(STATE, "pipelines.stopped")  # set by `stop`, cleared by `start`


def settings():
    try:
        with open(os.path.join(CONFIG, "pipelines.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def running_pid():
    """PID of our poller, or None. Checks the command line against PID reuse."""
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            if b"pipelines.py" in f.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def start():
    if running_pid():
        return "already running"
    cfg = settings()
    cmd = [sys.executable, os.path.join(HERE, "pipelines.py")]
    for key in ("target", "interval", "daynotes"):
        if key in cfg:
            cmd += [f"--{key}", str(cfg[key])]
    if "pinned" in cfg:
        cmd += ["--pinned", json.dumps(cfg["pinned"])]
    os.makedirs(STATE, exist_ok=True)
    if os.path.getsize(LOGFILE) > 1_000_000 if os.path.exists(LOGFILE) else False:
        os.replace(LOGFILE, LOGFILE + ".1")
    log = open(LOGFILE, "a")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                            start_new_session=True, cwd=HERE)
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))
    return f"started (pid {proc.pid})"


def stop():
    pid = running_pid()
    if not pid:
        return "not running"
    os.kill(pid, signal.SIGTERM)
    return f"stopped (pid {pid})"


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "ensure"
    os.makedirs(STATE, exist_ok=True)
    if action == "ensure":
        # Respect a deliberate stop and a disabled config
        if os.path.exists(STOPPED) or settings().get("enabled") is False:
            print("disabled")
        else:
            print(start())
    elif action == "start":
        if os.path.exists(STOPPED):
            os.remove(STOPPED)
        print(start())
    elif action == "stop":
        open(STOPPED, "w").close()
        print(stop())
    elif action == "restart":
        stop()
        if os.path.exists(STOPPED):
            os.remove(STOPPED)
        print(start())
    elif action == "status":
        pid = running_pid()
        print(f"running (pid {pid})" if pid else "not running")
        if os.path.exists(LOGFILE):
            with open(LOGFILE) as f:
                print("".join(f.readlines()[-5:]), end="")
    else:
        sys.exit(f"unknown action: {action}")


if __name__ == "__main__":
    main()
