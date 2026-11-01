# Agent and pipeline status from Herdr on the PC.
#
# herdr-plugin/notify.py sends {"status": "working", "list": [...]} to UDP
# port 47474 on every agent change, and herdr-plugin/pipelines.py sends
# {"type": "pipelines", ...} every 30 s plus the agent status again. When Herdr
# closes the poller says goodbye ("none"); if the PC just goes away the status
# fades out after a few minutes without updates.

import json
import network
import socket
import time

PORT = 47474
AGENT_STALE_MS = 3 * 60 * 1000
PIPE_STALE_MS = 3 * 60 * 1000  # the poller sends every 30 s
WAITING_STATES = ("running", "pending", "created", "preparing", "waiting_for_resource", "scheduled")

agent_status = None  # combined: working, blocked, done, idle
agent_list = []  # [{"w": workspace, "k": kind, "s": status, "t": title}, ...]
agent_rx = 0
pipe_status = None  # combined: running, failed, success
pipe_items = []  # [{"w": space, "n": MR or branch, "s": status, ...}, ...]
pipe_rx = 0

# Beeps come from changes of single agents and pipelines, not from the combined
# status, so one finishing while another keeps running is heard too. The main
# loop plays them and clears them.
agent_beep = None  # "done" or "alert"
pipe_beep = None  # "pipe_start", "pipe_ok" or "pipe_fail"
_agent_seen = {}  # (workspace, kind) -> last status
_pipe_seen = {}  # (space, MR or branch) -> last status

# Pipelines seen running or waiting since boot, with their last status, for
# the icons in the scene: [[(space, MR or branch), status], ...], oldest first
recent_pipes = []
MAX_RECENT = 5

_wlan = network.WLAN(network.STA_IF)
_sock = None


def _watch_agents(entries):
    global _agent_seen, agent_beep
    seen = {}
    for a in entries:
        key = (a.get("w"), a.get("k"))
        s, before = a.get("s"), _agent_seen.get(key)
        seen[key] = s
        if before is None or s == before:
            continue
        if s == "blocked":
            agent_beep = "alert"
        elif before == "working" and s in ("done", "idle") and agent_beep != "alert":
            agent_beep = "done"
    _agent_seen = seen


def _watch_pipes(items):
    global _pipe_seen, pipe_beep
    seen = {}
    for it in items:
        key = (it.get("w"), it.get("n"))
        s, before = it.get("s"), _pipe_seen.get(key)
        seen[key] = s
        if before is None or s == before:
            continue
        if s == "failed":
            pipe_beep = "pipe_fail"  # the most important one wins
        elif s == "success" and before in WAITING_STATES and pipe_beep != "pipe_fail":
            pipe_beep = "pipe_ok"
        elif s in WAITING_STATES and before not in WAITING_STATES and not pipe_beep:
            pipe_beep = "pipe_start"
    _pipe_seen = seen
    _track_pipes(items)


def _track_pipes(items):
    """Remember pipelines once they run; keep their last status after that."""
    for it in items:
        key, s = (it.get("w"), it.get("n")), it.get("s")
        for entry in recent_pipes:
            if entry[0] == key:
                entry[1] = s
                break
        else:
            if s in WAITING_STATES:
                recent_pipes.append([key, s])
    while len(recent_pipes) > MAX_RECENT:  # drop the oldest finished one
        for i, (_, s) in enumerate(recent_pipes):
            if s not in WAITING_STATES:
                del recent_pipes[i]
                break
        else:
            del recent_pipes[0]


def poll(now):
    """Read every waiting packet without blocking."""
    global agent_status, agent_list, agent_rx, pipe_status, pipe_items, pipe_rx, _sock
    if _sock is None:
        if not _wlan.isconnected():
            return
        try:
            _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _sock.bind(("0.0.0.0", PORT))
            _sock.setblocking(False)
        except OSError:
            _sock = None
            return
    while True:
        try:
            data = _sock.recv(4096)  # pipeline lists are ~1 KB, a smaller buffer drops them
        except OSError:
            break
        try:
            msg = json.loads(data)
            if msg.get("type") == "pipelines":
                pipe_status = msg["status"] if msg["status"] != "none" else None
                if pipe_status is None:  # Herdr closed
                    recent_pipes.clear()
                pipe_items = msg.get("items", [])
                _watch_pipes(pipe_items)
                pipe_rx = now
                continue
            agent_status = msg["status"]
            new_list = msg.get("list", [])
            _watch_agents(new_list)
            agent_list = new_list
            agent_rx = now
        except (ValueError, KeyError, TypeError):
            pass
    if agent_status and time.ticks_diff(now, agent_rx) > AGENT_STALE_MS:
        agent_status = None
        agent_list = []
    if pipe_status and time.ticks_diff(now, pipe_rx) > PIPE_STALE_MS:
        pipe_status = None
        pipe_items = []
        recent_pipes.clear()


def pipes_fresh(now):
    """Did the poller send anything lately?"""
    return bool(pipe_rx and time.ticks_diff(now, pipe_rx) < PIPE_STALE_MS)


def progress():
    """Share of jobs done (0..1) over all running pipelines together, or None."""
    done = total = 0
    for it in pipe_items:
        if it.get("s") == "running" and "/" in it.get("p", ""):
            d, t = (int(v) for v in it["p"].split("/"))
            done, total = done + d, total + t
    return done / total if total else None
