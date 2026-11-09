#!/usr/bin/env python3
"""Start, stop and keep alive the GitLab pipeline poller (pipelines.py).

Herdr has no supervised plugin daemons, so this follows the pattern other
GitLab plugins use: the startup hook and a few event hooks call `ensure`,
which starts the poller in the background unless it is already running. The
poller exits by itself when the Herdr server goes away.

  python3 poller_ctl.py ensure|start|stop|restart|status
  python3 poller_ctl.py run    # in the foreground, for the systemd service
  python3 poller_ctl.py install-service|uninstall-service

Without the Herdr TUI (the desktop app runs on herdr-core, `hc`, which has no
plugins) the poller runs as the systemd user service `presto-poller` instead
(see README); `ensure`/`start` then leave it to the service.

State (pidfile, log) lives in $HERDR_PLUGIN_STATE_DIR. Settings are read from
pipelines.json in $HERDR_PLUGIN_CONFIG_DIR, for example:

  {"interval": 30, "target": "255.255.255.255", "enabled": true,
   "pinned": [{"host": "gitlab.example.com", "project": "group/project",
               "ref": "develop"}],
   "daynotes": "05-tagebuch"}

"daynotes" is optional (see daynote.py): a folder inside the Obsidian vault,
an absolute path, or "off".
"""

import fcntl
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
LOCK = os.path.join(STATE, "pipelines.lock")


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


SERVICE = "presto-poller"


def command(*extra):
    cfg = settings()
    cmd = [sys.executable, os.path.join(HERE, "pipelines.py"), *extra]
    for key in ("target", "interval", "daynotes"):
        if key in cfg:
            cmd += [f"--{key}", str(cfg[key])]
    if "pinned" in cfg:
        cmd += ["--pinned", json.dumps(cfg["pinned"])]
    return cmd


def service_active():
    """True while the systemd user service runs the poller (one is enough,
    both would send the same computer's status)."""
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE],
                              timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def start():
    if running_pid():
        return "already running"
    if service_active():
        return f"runs as the service {SERVICE}"
    cmd = command()
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


UNIT = """[Unit]
Description=Presto: agents and pipelines from herdr-core (hc)
After=network-online.target

[Service]
Environment=HERDR_PLUGIN_CONFIG_DIR={config}
Environment=HERDR_PLUGIN_STATE_DIR={state}
ExecStart={python} {here}/poller_ctl.py run
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""


def unit_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "systemd", "user", SERVICE + ".service")


def plugin_dir(kind):
    """The plugin's config or state dir as Herdr knows it, also when called by hand."""
    env = os.environ.get(f"HERDR_PLUGIN_{kind.upper()}_DIR")
    if env:
        return env
    if kind == "config":
        try:
            out = subprocess.run(["herdr", "plugin", "config-dir", "presto.clawd"],
                                 capture_output=True, text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return HERE
    return os.path.join(HERE, ".state")


def systemctl(*args):
    subprocess.run(["systemctl", "--user", *args], check=True)


def install_service():
    """Runs the poller with the user's systemd, from boot on (with lingering)
    and restarted when it dies; for the Herdr desktop app (hc)."""
    stop()
    path = unit_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(UNIT.format(config=plugin_dir("config"), state=plugin_dir("state"),
                            python=sys.executable, here=HERE))
    systemctl("daemon-reload")
    systemctl("enable", "--now", SERVICE)
    systemctl("restart", SERVICE)  # picks up a changed unit
    return f"installed {path}, running"


def uninstall_service():
    path = unit_path()
    if os.path.exists(path):
        subprocess.run(["systemctl", "--user", "disable", "--now", SERVICE])
        os.remove(path)
        systemctl("daemon-reload")
    return "removed"


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "ensure"
    if action == "run":  # the service: agents and spaces from hc, never exits
        cmd = command("--source", "hc")
        os.execv(cmd[0], cmd)
    if action in ("install-service", "uninstall-service"):
        print(install_service() if action == "install-service" else uninstall_service())
        return
    os.makedirs(STATE, exist_ok=True)
    # the startup hook and the first events run at the same time: without the
    # lock both would start a poller and only one of them ends up in the pidfile
    lock = open(LOCK, "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
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
