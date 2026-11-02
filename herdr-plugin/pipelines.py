#!/usr/bin/env python3
"""Send the CI pipeline state of my active Herdr spaces to the Presto, where the
hamster jogs in its wheel while a pipeline runs.

Every 30 s it asks Herdr for its workspaces and the directories of their panes,
finds the git repos and checked out branches, and for each of those repos shows
  - the CI of the checked out branch (if it has any)
  - the CI of my open merge requests / pull requests in that repo (updated in
    the last 7 days), so nothing has to be checked out to be seen
GitLab via `glab api` (an MR's head pipeline, else the newest branch
pipeline), GitHub via `gh api` (newest Actions run). Pinned refs from the config (for
example a team's develop branch) are added. Running pipelines come first,
then failed ones, then the most recent.

It broadcasts one small JSON UDP packet (same port as the agent status), with
the computer's name, so the Presto can show several computers together:

  {"type": "pipelines", "src": "myhost", "status": "running|failed|success|none",
   "items": [{"w": "myspace", "n": "!42", "t": "title", "s": "running",
              "p": "3/5", "d": "4m", "a": "12m", "f": "test_backend", "i": 123456}, ...]}

Normally started and kept alive by the Herdr plugin (poller_ctl.py); it stops
by itself when the Herdr server is gone. glab/gh must be logged in.

  python3 pipelines.py                 # loop until Herdr exits
  python3 pipelines.py --once          # send once and print the payload
  python3 pipelines.py --target 192.168.1.50

It also sends the Herdr agent status (notify.py sends it on every change),
today's daily note (daynote.py): appointments and tasks, and Claude's usage
limits (usage.py). Between the rounds
everything goes out again every few seconds, so a Presto that just started
shows it at once.
"""

import argparse
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import quote

PORT = 47474
SOURCE = socket.gethostname()[:16]  # the Presto keeps the status of each computer apart
AGENT_EVERY = 5  # s between status messages (new pipeline data: every --interval)
MAX_ITEMS = 5  # rows on the Presto's screen
RECENT_S = 7 * 86400  # my MRs/PRs older than this are left out
RUNNING = ("running", "pending", "created", "preparing", "waiting_for_resource", "scheduled")
UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
DEFAULT_PINNED = []  # set "pinned" in pipelines.json, e.g. a team's develop branch


def ascii_text(text, length):
    """The Presto's bitmap font only has ASCII."""
    return (text or "").translate(UMLAUTS).encode("ascii", "ignore").decode().strip()[:length]


def run_json(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError((out.stderr or out.stdout).strip()[:200] or f"{cmd[0]} failed")
    return json.loads(out.stdout)


def short_duration(seconds):
    seconds = int(seconds or 0)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def timing(item, status, started, finished, duration, updated):
    now = datetime.now(timezone.utc)
    if status in RUNNING and started:
        item["d"] = short_duration((now - started).total_seconds())
    elif duration:  # also right for GitLab pipelines parked at a manual job
        item["d"] = short_duration(duration)
    elif started and finished:
        item["d"] = short_duration((finished - started).total_seconds())
    if updated:
        item["a"] = short_duration((now - updated).total_seconds())
        item["_age"] = (now - updated).total_seconds()  # for sorting, not sent


def age_s(value):
    t = parse_time(value)
    return (datetime.now(timezone.utc) - t).total_seconds() if t else 1e12


# --- Herdr spaces -------------------------------------------------------------

def herdr(*args):
    return run_json([os.environ.get("HERDR_BIN_PATH", "herdr"), *args])["result"]


def git(path, *args):
    out = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=10)
    return out.stdout.strip() if out.returncode == 0 else None


def parse_remote(url):
    """https://host/group/proj.git, git@host:group/proj.git, ssh://git@host:22/group/proj"""
    m = re.match(r"^(?:https?|ssh)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)(?:\.git)?/?$", url or "") \
        or re.match(r"^(?:[^@]+@)?([^:/]+):(.+?)(?:\.git)?/?$", url or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def active_spaces():
    """[(space label, host, project, branch)] in sidebar order, one per repo+branch."""
    workspaces = sorted(herdr("workspace", "list")["workspaces"], key=lambda w: w.get("number", 0))
    panes = herdr("pane", "list")["panes"]
    seen, spaces = {}, []
    for ws in workspaces:
        for pane in panes:
            if pane.get("workspace_id") != ws["workspace_id"]:
                continue
            cwd = pane.get("foreground_cwd") or pane.get("cwd")
            if not cwd or not git(cwd, "rev-parse", "--is-inside-work-tree"):
                continue
            host, project = parse_remote(git(cwd, "remote", "get-url", "origin"))
            branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
            if not host or not branch or branch == "HEAD":
                continue
            key = (host, project, branch)
            label = ws.get("label") or ws["workspace_id"]
            if key in seen:
                if label not in seen[key][0]:
                    seen[key][0].append(label)
                continue
            seen[key] = ([label], host, project, branch)
            spaces.append(seen[key])
    return [("+".join(labels), host, project, branch) for labels, host, project, branch in spaces]


# --- GitLab -------------------------------------------------------------------

def gitlab(host, project, path):
    return run_json(["glab", "api", "--hostname", host, f"projects/{quote(project, safe='')}/{path}"])


_me = {}


def gitlab_me(host):
    if host not in _me:
        _me[host] = run_json(["glab", "api", "--hostname", host, "user"])["username"]
    return _me[host]


def gitlab_describe(host, project, pipeline, item):
    item["s"] = pipeline["status"]
    item["i"] = pipeline["id"]  # the same pipeline from two computers is shown once
    jobs = gitlab(host, project, f"pipelines/{pipeline['id']}/jobs?per_page=100")
    counted = [j for j in jobs if j["status"] not in ("manual", "skipped", "canceled")]
    if counted:
        item["p"] = f"{sum(j['status'] in ('success', 'failed') for j in counted)}/{len(counted)}"
    failed = [j["name"] for j in jobs if j["status"] == "failed" and not j.get("allow_failure")]
    if failed:
        item["f"] = ascii_text(failed[0], 24)
    timing(item, item["s"], parse_time(pipeline.get("started_at")), parse_time(pipeline.get("finished_at")),
           pipeline.get("duration"), parse_time(pipeline.get("updated_at")))
    return item


def gitlab_item(host, project, ref, label):
    """CI of one branch: its open MR's head pipeline, else its newest pipeline."""
    item = {"w": ascii_text(label, 14), "n": ascii_text(ref, 30), "s": "none"}
    mrs = gitlab(host, project, f"merge_requests?state=opened&source_branch={quote(ref, safe='')}&per_page=1")
    pipeline = None
    if mrs:
        mr = gitlab(host, project, f"merge_requests/{mrs[0]['iid']}")
        item["n"], item["t"] = f"!{mr['iid']}", ascii_text(mr["title"], 60)
        pipeline = mr.get("head_pipeline")
    if not pipeline:
        latest = gitlab(host, project, f"pipelines?ref={quote(ref, safe='')}&per_page=1")
        if latest:
            pipeline = gitlab(host, project, f"pipelines/{latest[0]['id']}")
            if "t" not in item:
                try:
                    item["t"] = ascii_text(gitlab(host, project, f"repository/commits/{pipeline['sha']}")["title"], 60)
                except Exception:
                    pass
    return gitlab_describe(host, project, pipeline, item) if pipeline else item


def gitlab_mine(host, project, label, skip):
    """Head pipelines of my open, recently updated MRs; skip = branches already shown."""
    items = []
    mrs = gitlab(host, project, f"merge_requests?state=opened&author_username={gitlab_me(host)}"
                                "&order_by=updated_at&per_page=10")
    for mr in mrs:
        if mr["source_branch"] in skip or age_s(mr["updated_at"]) > RECENT_S:
            continue
        pipeline = gitlab(host, project, f"merge_requests/{mr['iid']}").get("head_pipeline")
        if pipeline and age_s(pipeline.get("updated_at")) <= RECENT_S:
            item = {"w": ascii_text(label, 14), "n": f"!{mr['iid']}", "t": ascii_text(mr["title"], 60)}
            items.append(gitlab_describe(host, project, pipeline, item))
    return items


# --- GitHub -------------------------------------------------------------------

GH_STATUS = {"queued": "pending", "waiting": "pending", "requested": "pending", "pending": "pending",
             "in_progress": "running"}
GH_CONCLUSION = {"success": "success", "failure": "failed", "timed_out": "failed", "startup_failure": "failed",
                 "cancelled": "canceled", "skipped": "skipped", "action_required": "manual", "neutral": "success"}


def github_describe(project, run, item):
    item["i"] = run["id"]
    if run["status"] == "completed":
        item["s"] = GH_CONCLUSION.get(run.get("conclusion"), "success")
    else:
        item["s"] = GH_STATUS.get(run["status"], "running")
    item.setdefault("t", ascii_text(run.get("display_title") or run.get("name"), 40))
    jobs = run_json(["gh", "api", f"repos/{project}/actions/runs/{run['id']}/jobs?per_page=100"])["jobs"]
    counted = [j for j in jobs if j.get("conclusion") not in ("skipped", "cancelled")]
    if counted:
        item["p"] = f"{sum(j['status'] == 'completed' for j in counted)}/{len(counted)}"
    failed = [j["name"] for j in jobs if j.get("conclusion") == "failure"]
    if failed:
        item["f"] = ascii_text(failed[0], 24)
    started, updated = parse_time(run.get("run_started_at")), parse_time(run.get("updated_at"))
    timing(item, item["s"], started, updated if run["status"] == "completed" else None, None, updated)
    return item


def github_runs(project, ref):
    return run_json(["gh", "api", f"repos/{project}/actions/runs?branch={quote(ref, safe='')}&per_page=1"])["workflow_runs"]


def github_item(project, ref, label):
    """CI of one branch: its newest Actions run, named after its open PR."""
    item = {"w": ascii_text(label, 14), "n": ascii_text(ref, 30), "s": "none"}
    owner = project.split("/")[0]
    prs = run_json(["gh", "api", f"repos/{project}/pulls?state=open&head={owner}:{quote(ref, safe='')}&per_page=1"])
    if prs:
        item["n"], item["t"] = f"#{prs[0]['number']}", ascii_text(prs[0]["title"], 60)
    runs = github_runs(project, ref)
    return github_describe(project, runs[0], item) if runs else item


def github_mine(project, label, skip):
    if "github" not in _me:
        _me["github"] = run_json(["gh", "api", "user"])["login"]
    items = []
    for pr in run_json(["gh", "api", f"repos/{project}/pulls?state=open&sort=updated&direction=desc&per_page=20"]):
        ref = pr["head"]["ref"]
        if pr["user"]["login"] != _me["github"] or ref in skip or age_s(pr["updated_at"]) > RECENT_S:
            continue
        runs = github_runs(project, ref)
        if runs:
            item = {"w": ascii_text(label, 14), "n": f"#{pr['number']}", "t": ascii_text(pr["title"], 60)}
            items.append(github_describe(project, runs[0], item))
    return items


# --- collect & send -------------------------------------------------------------

def safely(what, fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        print(f"{what}: {e}", flush=True)
        return None


ORDER = {"running": 0, "pending": 0, "created": 0, "preparing": 0, "waiting_for_resource": 0,
         "scheduled": 0, "failed": 1, "manual": 2, "success": 3}


def collect(pinned):
    items, shown = [], set()  # shown: (host, project, ref)
    spaces = active_spaces()
    # checked out branches
    for label, host, project, branch in spaces:
        github = "github" in host
        item = safely(f"{label} {project}@{branch}", github_item if github else gitlab_item,
                      *((project, branch, label) if github else (host, project, branch, label)))
        if item and item["s"] != "none":
            items.append(item)
        shown.add((host, project, branch))
    # my open MRs / PRs in every repo of a space
    repos = {}
    for label, host, project, branch in spaces:
        repos.setdefault((host, project), label.split("+")[0])
    for (host, project), label in repos.items():
        skip = {ref for h, p, ref in shown if (h, p) == (host, project)}
        mine = safely(f"{label} {project} mine", github_mine if "github" in host else gitlab_mine,
                      *((project, label, skip) if "github" in host else (host, project, label, skip)))
        items += mine or []
    # pinned refs like develop
    for pin in pinned:
        if (pin["host"], pin["project"], pin["ref"]) not in shown:
            # listed under the space that has the repo open, else the project name
            label = repos.get((pin["host"], pin["project"])) or pin["project"].rsplit("/", 1)[-1]
            github = "github" in pin["host"]
            item = safely(f"pinned {pin['ref']}", github_item if github else gitlab_item,
                          *((pin["project"], pin["ref"], label) if github
                            else (pin["host"], pin["project"], pin["ref"], label)))
            if item and item["s"] != "none":
                items.append(item)

    items.sort(key=lambda i: (ORDER.get(i["s"], 4), i.get("_age", 1e12)))
    items = items[:MAX_ITEMS]
    for i in items:
        i.pop("_age", None)
    states = [i["s"] for i in items]
    if any(s in RUNNING for s in states):
        overall = "running"
    elif "failed" in states:
        overall = "failed"
    elif states:
        overall = "success"
    else:
        overall = "none"
    return {"type": "pipelines", "src": SOURCE, "status": overall, "items": items}


def herdr_alive():
    """True while the Herdr server's socket accepts connections."""
    path = os.environ.get("HERDR_SOCKET_PATH")
    if not path:
        return True  # started by hand, outside Herdr
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(path)
        return True
    except OSError:
        return False


def agent_payload():
    """The Herdr agent status too, so the Presto catches up after a restart
    without waiting for the next status change."""
    import notify  # same directory
    return json.dumps(notify.agent_status(), separators=(",", ":")).encode()


def day_payload(setting):
    """Today's daily note, pulled from git first now and then; None when this
    computer has no vault (another one may have it)."""
    import daynote  # same directory
    folder = daynote.find_folder(setting or None)
    if not folder:
        return None
    daynote.pull(folder)
    return json.dumps(dict(daynote.collect(folder), src=SOURCE), separators=(",", ":")).encode()


def usage_payload():
    """Claude's usage limits as saved by the status line; None without."""
    import usage  # same directory
    msg = usage.collect(SOURCE)
    return json.dumps(msg, separators=(",", ":")).encode() if msg else None


def send_agents(sock, target):
    try:
        sock.sendto(agent_payload(), (target, PORT))
    except Exception as e:  # Herdr busy, ...
        print(f"agent status: {e}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", default="255.255.255.255", help="Presto IP, default is broadcast")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--pinned", help='JSON list like [{"host":..,"project":..,"ref":"develop"}], "[]" for none')
    ap.add_argument("--daynotes", default="",
                    help="folder of the daily notes inside the Obsidian vault or an absolute path, "
                         "default: found in the vaults; off: don't send")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    pinned = json.loads(args.pinned) if args.pinned else DEFAULT_PINNED

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    misses = 0
    latest = []  # the last pipeline and daily note messages, sent again between the rounds
    while True:
        if not args.once:
            misses = 0 if herdr_alive() else misses + 1
            if misses >= 3:
                # tell the Presto that nothing is going on any more, so Clawd
                # and Messy don't keep working after Herdr was closed
                for msg in ({"src": SOURCE, "status": "none", "agents": 0, "count": 0, "title": "", "list": []},
                            {"type": "pipelines", "src": SOURCE, "status": "none", "items": []},
                            {"type": "day", "src": SOURCE, "date": None, "note": 0, "events": [], "tasks": []},
                            {"type": "usage", "src": SOURCE}):
                    for _ in range(3):
                        sock.sendto(json.dumps(msg).encode(), (args.target, PORT))
                        time.sleep(0.05)
                print("herdr is gone, said goodbye to the Presto, exiting", flush=True)
                break
        try:
            payload = json.dumps(collect(pinned), separators=(",", ":")).encode()
            latest = [payload]
            for _ in range(2):  # UDP may drop a packet now and then
                sock.sendto(payload, (args.target, PORT))
                time.sleep(0.05)
            send_agents(sock, args.target)
            if args.daynotes != "off":
                try:
                    day = day_payload(args.daynotes)
                    if day:
                        latest.append(day)
                        sock.sendto(day, (args.target, PORT))
                        if args.once:
                            print(day.decode())
                except Exception as e:
                    print(f"daily note: {e}", flush=True)
            try:
                use = usage_payload()
                if use:
                    latest.append(use)
                    sock.sendto(use, (args.target, PORT))
                    if args.once:
                        print(use.decode())
            except Exception as e:
                print(f"usage: {e}", flush=True)
            if args.once:
                print(payload.decode())
            else:
                states = " ".join(f"{i['w']}:{i['n']}={i['s']}" for i in json.loads(payload)["items"])
                print(f"{time.strftime('%H:%M:%S')} sent {len(payload)} B: {states}", flush=True)
        except Exception as e:  # Herdr busy, network hiccup, ...
            print(f"error: {e}", flush=True)
        if args.once:
            break
        # between the rounds the agent status and the last pipelines and daily
        # note go out again every few seconds, so a Presto that just started
        # knows them quickly
        until = time.time() + args.interval
        while time.time() < until:
            time.sleep(max(0.0, min(AGENT_EVERY, until - time.time())))
            send_agents(sock, args.target)
            for msg in latest + latest[:1]:  # the pipelines twice: big packets get lost more often
                try:
                    sock.sendto(msg, (args.target, PORT))
                    time.sleep(0.2)  # the Presto's radio only buffers a few packets
                except OSError as e:
                    print(f"resend: {e}", flush=True)


if __name__ == "__main__":
    main()
