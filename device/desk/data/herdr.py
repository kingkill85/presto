# Agent and pipeline status from Herdr on the PC, and today's daily note.
#
# herdr-plugin/notify.py sends {"status": "working", "list": [...]} to UDP
# port 47474 on every agent change, and herdr-plugin/pipelines.py sends
# {"type": "pipelines", ...} and {"type": "day", ...} (herdr-plugin/daynote.py)
# every 30 s plus the agent status again. When Herdr
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
pipe_status = None  # combined: running, failed, success
pipe_items = []  # [{"w": space, "n": MR or branch, "s": status, ...}, ...]
pipe_rx = 0
day = None  # today's daily note: {"date", "note": 0/1, "place", "events": [{"t", "n", "x"}], "tasks": [{"n", "x"}]}

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


# Several computers can run Herdr at the same time: every message names its
# computer ("src"), each one's status is kept apart and they are shown merged.
AGENT_ORDER = ("blocked", "working", "done", "idle", "unknown")  # the combined status: the first one found
_agents = {}  # src -> [status, list, received]
_pipes = {}  # src -> [status, items, received]
_days = {}  # src -> [message, received]


def _urgency(item):
    s = item.get("s")
    return 0 if s in WAITING_STATES else 1 if s == "failed" else 2


def _merge():
    """The combined status of all computers."""
    global agent_status, agent_list, pipe_status, pipe_items, pipe_rx, day
    agents, states = [], []
    for src in sorted(_agents):
        status, items, _ = _agents[src]
        agents += items
        states.append(status)
    agent_status = next((s for s in AGENT_ORDER if s in states), None)
    _watch_agents(agents)
    agent_list = agents
    items, states, pipe_rx = [], [], 0
    for src in sorted(_pipes):
        status, its, rx = _pipes[src]
        items += its
        states.append(status)
        pipe_rx = rx
    items.sort(key=_urgency)  # running ones first, then failed (sort is stable)
    pipe_status = "running" if "running" in states else "failed" if "failed" in states else \
        "success" if states else None
    _watch_pipes(items)
    pipe_items = items
    if not _pipes:
        recent_pipes.clear()
    notes = sorted(_days.values(), key=lambda v: (bool(v[0].get("note")), v[1]))  # one with a note wins
    day = notes[-1][0] if notes else None


def _receive(msg, now):
    src = msg.get("src", "")
    kind = msg.get("type")
    if kind == "day":
        if msg.get("date"):
            _days[src] = [msg, now]
        else:  # no date: Herdr closed there
            _days.pop(src, None)
    elif kind == "pipelines":
        if msg["status"] == "none":  # no pipelines there, or Herdr closed
            _pipes.pop(src, None)
        else:
            _pipes[src] = [msg["status"], msg.get("items", []), now]
    elif msg["status"] == "none":
        _agents.pop(src, None)
    else:
        _agents[src] = [msg["status"], msg.get("list", []), now]


def poll(now):
    """Read every waiting packet without blocking; forget computers that went
    quiet."""
    global _sock
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
    changed = False
    while True:
        try:
            data = _sock.recv(4096)  # pipeline lists are ~1 KB, a smaller buffer drops them
        except OSError:
            break
        try:
            _receive(json.loads(data), now)
            changed = True
        except (ValueError, KeyError, TypeError):
            pass
    for table, stale_ms in ((_agents, AGENT_STALE_MS), (_pipes, PIPE_STALE_MS), (_days, PIPE_STALE_MS)):
        for src in [src for src, v in table.items() if time.ticks_diff(now, v[-1]) > stale_ms]:
            del table[src]
            changed = True
    if changed:
        _merge()


def next_event(t):
    """The appointment that comes next (or started less than 15 min ago) and
    isn't ticked off, for the local time t (None: the first open one)."""
    if not day or not day.get("note"):
        return None
    minute = t[3] * 60 + t[4] - 15 if t else -1
    for e in day["events"]:
        hh, mm = e["t"].split(":")
        if not e.get("x") and int(hh) * 60 + int(mm) >= minute:
            return e
    return None


def minutes_until(e, t):
    hh, mm = e["t"].split(":")
    return int(hh) * 60 + int(mm) - (t[3] * 60 + t[4])


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
