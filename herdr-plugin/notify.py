#!/usr/bin/env python3
"""Send the combined status of all Herdr agents to the Presto.

Runs on every agent status change. Picks the most important status across all
agents (blocked > working > done > idle: as long as one agent still works, the
Presto shows work) and sends it, together with a short
list of all agents, as a small JSON UDP packet. By default it is broadcast on
the local network, so the Presto's IP doesn't need to be known. To send to a fixed address instead, put
"192.168.1.50" (or "host:port") into the file `target` in the plugin's config
directory (`herdr plugin config-dir presto.clawd`). In WSL2 the broadcast goes
out through Windows (udp.py).
"""

import json
import os
import socket
import subprocess
import time

import udp  # same directory

PORT = 47474
PRIORITY = ("blocked", "working", "done", "idle", "unknown")
SOURCE = socket.gethostname()[:16]  # the Presto keeps the status of each computer apart
MAX_LISTED = 5  # what fits on the Presto's screen
UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def ascii_text(text, length):
    """The Presto's bitmap font only has ASCII."""
    text = text.translate(UMLAUTS).encode("ascii", "ignore").decode().strip()
    return text[:length]


def herdr_json(*args):
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    out = subprocess.run([herdr, *args], capture_output=True, text=True, timeout=10).stdout
    return json.loads(out)["result"]


def herdr_agents():
    """The Herdr TUI's agents: [{"workspace", "agent", "title", "status"}]"""
    agents = herdr_json("agent", "list")["agents"]
    try:
        labels = {w["workspace_id"]: w.get("label") or "" for w in herdr_json("workspace", "list")["workspaces"]}
    except Exception:
        labels = {}
    return [
        {
            "workspace": labels.get(a.get("workspace_id"), "") or a.get("workspace_id", ""),
            "agent": a.get("agent") or "",
            "title": a.get("terminal_title_stripped") or "",
            "status": a.get("agent_status", "unknown"),
        }
        for a in agents
    ]


def agent_status(agents=None):
    """The message for the Presto; agents from Herdr unless given (hc.agents)."""
    if agents is None:
        agents = herdr_agents()
    listed = [
        {
            "w": ascii_text(a["workspace"], 14),
            "k": ascii_text(a["agent"], 10),
            "t": ascii_text(a["title"], 34),
            "s": a["status"],
        }
        for a in agents[:MAX_LISTED]
    ]
    by_status = {}
    for a in agents:
        by_status.setdefault(a["status"], []).append(a)
    for status in PRIORITY:
        if status in by_status:
            first = by_status[status][0]
            return {
                "src": SOURCE,
                "status": status,
                "agents": len(agents),
                "count": len(by_status[status]),
                "title": ascii_text(first["title"], 34),
                "list": listed,
            }
    return {"src": SOURCE, "status": "none", "agents": 0, "count": 0, "title": "", "list": []}


def target():
    host, port = "255.255.255.255", PORT
    config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if config_dir:
        try:
            with open(os.path.join(config_dir, "target")) as f:
                value = f.read().strip()
            if value:
                host, _, p = value.partition(":")
                port = int(p) if p else PORT
        except OSError:
            pass
    return host, port


def main():
    payload = json.dumps(agent_status(), separators=(",", ":")).encode()
    sock = udp.Sender()
    addr = target()
    for _ in range(3):  # UDP may drop a packet now and then
        sock.sendto(payload, addr)
        time.sleep(0.05)
    sock.close()
    print(payload.decode())


if __name__ == "__main__":
    main()
