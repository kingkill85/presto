#!/usr/bin/env python3
"""Today's daily note (Obsidian or any folder of YYYY-MM-DD.md files) for the
Presto: the appointments and tasks, as one small JSON message

  {"type": "day", "date": "2026-10-16", "note": 1, "place": "home",
   "events": [{"t": "09:00", "n": "Daily Standup", "x": 1}, ...],
   "tasks": [{"n": "Retro-Vorbereitung", "x": 0}, ...]}

Appointments are the list items under "## Termine" with a time like (13:00),
tasks the list items under "## Aufgaben"; "x" is 1 when the box is ticked.
Wikilinks show their alias, bold and links are stripped. There is only a note
on work days: "note" is 0 on weekends and holidays. "place" is "home" or
"office" when a line like "> Homeoffice-Tag." or "> Büro-Tag ..." says so.

The folder differs from computer to computer, so it is looked up in the
vaults Obsidian knows (obsidian.json): the folder of the Daily notes plugin,
else DEFAULT_FOLDER. A setting can name another folder inside the vault, or
an absolute path. When the vault is a git repository (synced between
computers), it is pulled every PULL_S seconds first, fast-forward only, so a
note written on another computer shows up; local changes are never touched.

  python3 daynote.py                     # print today's message
  python3 daynote.py /path/to/notes      # from that folder
"""

import json
import os
import re
import subprocess
import sys
import time

DEFAULT_FOLDER = "05-tagebuch"  # inside the vault
OBSIDIAN_CONFIGS = (  # where Obsidian lists its vaults
    "~/.config/obsidian/obsidian.json",
    "~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json",  # Flatpak
    "~/Library/Application Support/obsidian/obsidian.json",  # macOS
)
PULL_S = 300
EVENTS = "Termine"  # section headings in the note
TASKS = "Aufgaben"
MAX_EVENTS = 8
MAX_TASKS = 10
NAME_LEN = 40
UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})

ITEM = re.compile(r"^\s*[-*+]\s+(?:\[( |x|X)\]\s+)?(.*)$")
TIME = re.compile(r"\(?\b(\d{1,2})[:.](\d{2})\b(?:\s*(?:-|–|bis)\s*\d{1,2}[:.]\d{2})?\)?(?:\s*Uhr)?")
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MDLINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def ascii_text(text):
    """The Presto's bitmap font only has ASCII."""
    text = text.translate(UMLAUTS).replace("–", "-").replace("→", "->")
    return " ".join(text.encode("ascii", "ignore").decode().split())


def plain(text):
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1).rsplit("/", 1)[-1], text)
    text = MDLINK.sub(r"\1", text)
    return text.replace("`", "")


def cut(text, n):
    """At most n characters, cut at a word boundary."""
    if len(text) <= n:
        return text
    text = text[:n + 1]
    return text[:text.rfind(" ")] if " " in text[n // 2:] else text[:n]


def title(text):
    """A short name: the bold part if the item starts with one, followed by
    the start of the rest when the bold part is short (a ticket, a name)."""
    text = plain(text)
    m = re.match(r"\s*\*\*(.+?)\*\*\s*(.*)", text)
    if m:
        head, rest = m.group(1).strip(), m.group(2).lstrip(" :")
        colon = head.endswith(":") or m.group(2).lstrip().startswith(":")
        head = head.rstrip(" :")
        if len(head) < 20 and rest:
            head += (": " if colon else " ") + rest
    else:
        head = text
    head = ascii_text(head.replace("**", "").replace("__", ""))
    return cut(head, NAME_LEN).rstrip(" :-,")


def sections(lines):
    """{heading: [lines]} for the ## headings."""
    out, current = {}, None
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None and not line.startswith("#"):
            out[current].append(line)
    return out


def items(lines):
    for line in lines:
        m = ITEM.match(line)
        if m and m.group(2).strip():
            yield m.group(1) in ("x", "X"), m.group(2)


def vaults():
    """Paths of the vaults Obsidian knows on this computer, open ones first."""
    for name in OBSIDIAN_CONFIGS:
        try:
            with open(os.path.expanduser(name)) as f:
                known = json.load(f).get("vaults", {}).values()
        except (OSError, ValueError):
            continue
        return [v["path"] for v in sorted(known, key=lambda v: not v.get("open")) if v.get("path")]
    return []


def daily_folder(vault):
    try:
        with open(os.path.join(vault, ".obsidian", "daily-notes.json")) as f:
            return json.load(f).get("folder") or DEFAULT_FOLDER
    except (OSError, ValueError):
        return DEFAULT_FOLDER


def find_folder(setting=None):
    """The folder with the daily notes, or None."""
    if setting and os.path.isabs(os.path.expanduser(setting)):
        return os.path.expanduser(setting)
    for vault in vaults():
        folder = os.path.join(vault, setting or daily_folder(vault))
        if os.path.isdir(folder):
            return folder
    return None


_pulled = 0


def pull(folder):
    """git pull --ff-only the vault now and then, if it is a repository."""
    global _pulled
    if not folder or time.time() - _pulled < PULL_S:
        return
    _pulled = time.time()
    try:
        subprocess.run(["git", "-C", folder, "pull", "--ff-only", "--quiet"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


PLACE_LINE = re.compile(r"^\s*(>|\*\*|-\s*(?!\[))")  # quotes, bold labels, plain bullets (no tasks)
HOME = re.compile(r"home\s*-?\s*office", re.I)
OFFICE = re.compile(r"b(ü|ue)ro", re.I)


def place(lines):
    """"home", "office" or None from the first line that says where."""
    for line in lines:
        if not PLACE_LINE.match(line):
            continue
        if HOME.search(line):
            return "home"
        if OFFICE.search(line):
            return "office"
    return None


def collect(folder, day=None):
    """The message for the note of `day` (default today) in `folder`."""
    day = day or time.strftime("%Y-%m-%d")
    msg = {"type": "day", "date": day, "note": 0, "place": None, "events": [], "tasks": []}
    if not folder:
        return msg
    try:
        with open(os.path.join(folder, day + ".md"), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return msg  # no note: not a work day (or not written yet)
    parts = sections(lines)
    msg["note"] = 1
    msg["place"] = place(parts.get(EVENTS, []) + lines)  # usually said under the appointments
    for done, text in items(parts.get(EVENTS, [])):
        m = TIME.search(text)
        if not m:
            continue
        name = title(TIME.sub("", text, count=1))
        msg["events"].append({"t": "%02d:%s" % (int(m.group(1)), m.group(2)), "n": name, "x": int(done)})
    msg["events"].sort(key=lambda e: e["t"])
    del msg["events"][MAX_EVENTS:]
    for done, text in items(parts.get(TASKS, [])):
        name = title(text)
        if name:
            msg["tasks"].append({"n": name, "x": int(done)})
    msg["tasks"].sort(key=lambda t: t["x"])  # open ones first
    del msg["tasks"][MAX_TASKS:]
    return msg


if __name__ == "__main__":
    folder = find_folder(sys.argv[1] if len(sys.argv) > 1 else None)
    print("folder:", folder, file=sys.stderr)
    print(json.dumps(collect(folder, sys.argv[2] if len(sys.argv) > 2 else None), ensure_ascii=False, indent=1))
