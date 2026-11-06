# The pages next to the scene: today, agents, pipelines, home, settings and apps.
#
# They hardly move, so each one is only drawn (and sent to the screen) again
# when its key changes: the data it shows plus a clock tick for every blink or
# spinner that is visible right now. That saves ~20 ms per frame.

import network

from desk import prefs, sound
from desk.data import ha, herdr
from desk.gfx import (ALERT_PEN, CLAWD_PEN, CLOCK, CROSS, DIM_PEN, EXCL, FAIL_PEN, FUR_PEN, GEAR_A,
                       GEAR_B, HEIGHT, IDLE_PEN, MANUAL_PEN, PLAY, QMARK, RING, RING_SMALL,
                       SLASH, SPARK, SPARK_X, TEXT_PEN, TICK, TICK_PEN, WHEEL_PEN, WIDTH, display, draw_art,
                       draw_colour_art, draw_degrees, pen, presto)
from desk.scene import scene, seasons
from desk.scene.scene import draw_weather_icon

wlan = network.WLAN(network.STA_IF)
VIEWS = ("scene", "today", "agents", "pipelines", "home", "settings", "apps")  # swipe order
climate = None  # optional BME280, supplied by the main loop
pad_focus = None  # (view, index), only visible when a gamepad is connected

MINI_HAMSTER = (".#....#.", "########", "##.##.##", "########", ".######.")
MINI_CLAWD = (".######.", ".#.##.#.", "########", ".######.", ".#.#.#.#")
HOUSE = ("..#..", ".###.", "#####", "#.#.#", "#.#.#")
GEAR = (".#.#.", "#####", "##.##", "#####", ".#.#.")
FLAME = ("..#..", ".##..", ".###.", "#####", ".###.")
BULB = (".###.", "#####", "#####", ".###.", ".#.#.")
GRID = ("##.##", "##.##", ".....", "##.##", "##.##")
FLAME_PEN = pen((255, 120, 30))
BULB_OFF_PEN = pen((70, 70, 90))


def draw_page_dots(view):
    i0 = VIEWS.index(view)
    x0 = WIDTH // 2 - (len(VIEWS) * 12 - 6) // 2
    for i in range(len(VIEWS)):
        display.set_pen(TEXT_PEN if i == i0 else DIM_PEN)  # also on the scene, before any theme
        display.rectangle(x0 + i * 12, HEIGHT - 8, 6, 6)


# --- the look of every page ------------------------------------------------------
# The colours follow the sky of the scene (dark at night, blue by day): tiles
# a shade lighter (or darker by day), flat with rounded corners. A garland for
# the season hangs across the top, a few pixel sparkles in the background,
# the title has a drop shadow.

BOTTOM = HEIGHT - 12  # above the page dots
SPARKLES = [(((i * 53 + 17) % (WIDTH - 8)) // 4 * 4, (40 + (i * 71) % (BOTTOM - 50)) // 4 * 4) for i in range(14)]
BG = TILE = SHADE = MUTED = None  # set from the sky before each page is drawn
_theme_of = None
_now = 0  # time of the page being drawn


def set_theme(rgb):
    """Page colours from the sky colour rgb."""
    global BG, TILE, SHADE, MUTED, _theme_of
    if rgb == _theme_of:
        return
    _theme_of = rgb
    r, g, b = rgb
    BG = pen(rgb)
    if (r + g + b) // 3 < 70:  # dark sky: lighter tiles
        TILE = pen((min(255, r + 16), min(255, g + 17), min(255, b + 27)))
        MUTED = DIM_PEN
    else:  # bright sky: darker tiles, so white writing stays readable
        TILE = pen((r * 4 // 5, g * 4 // 5, b * 4 // 5))
        MUTED = pen(((r + 255) // 2, (g + 255) // 2, (b + 255) // 2))  # quieter writing, half way to white
    SHADE = pen((r // 2, g // 2, b // 2))


# Garlands, 4 px pixel art repeated every 16 px along the top edge (no
# string, like the game menus); x takes the colour that alternates along it
GARLANDS = {
    "spring": ((".x.", "xyx", ".x."), (pen((200, 140, 170)), pen((235, 235, 240))), pen((220, 200, 110))),
    "summer": (("xxx", ".x."), (pen((150, 185, 225)), pen((225, 230, 240))), None),
    "autumn": (("xx.", "xxx", ".x."), (pen((205, 125, 55)), pen((160, 95, 55)), pen((190, 150, 60))), None),
    "winter": (("xxx", ".x.", ".x."), (pen((200, 214, 235)),), None),
    "lights": ((".y.", ".x."), (pen((220, 70, 70)), pen((230, 200, 80)), pen((90, 190, 110)), pen((90, 150, 230))),
               pen((60, 60, 70))),
}
ICICLES = (2, 1, 3, 1, 2, 3)  # rows of each icicle along the winter garland


def garland_kind(now):
    t = seasons.today(now)
    return "lights" if seasons.holiday(t) == "tree" else seasons.season(t)


def draw_garland(now):
    kind = garland_kind(now)
    art, colours, second = GARLANDS[kind]
    step = (now // 700) if kind == "lights" else 0  # the lights take turns
    for i, bx in enumerate(range(2, WIDTH, 16)):
        rows = art[:ICICLES[i % len(ICICLES)]] if kind == "winter" else art
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == ".":
                    continue
                display.set_pen(colours[(i + step) % len(colours)] if ch == "x" else second)
                display.rectangle(bx + c * 4, r * 4, 4, 4)


def draw_panel(x, y, w, h, hi=None):
    """A flat tile with rounded corners; hi: a coloured outline (alerts)."""
    if hi:
        display.set_pen(hi)
        display.rectangle(x, y, w, h)
        display.set_pen(TILE)
        display.rectangle(x + 2, y + 2, w - 4, h - 4)
    else:
        display.set_pen(TILE)
        display.rectangle(x, y, w, h)
    display.set_pen(BG)
    for cx, cy in ((x, y), (x + w - 2, y), (x, y + h - 2), (x + w - 2, y + h - 2)):
        display.rectangle(cx, cy, 2, 2)


def draw_header(art, x, y, colour, title):
    """Clear the page and draw its frame and title."""
    display.set_pen(BG)
    display.clear()
    display.set_pen(TILE)
    for sx, sy in SPARKLES:
        display.rectangle(sx, sy, 4, 4)
    draw_garland(_now)
    draw_art(art, x, y + 6, 3, colour)
    display.set_pen(SHADE)
    display.text(title, 44, 18, -1, 2)
    display.set_pen(TEXT_PEN)
    display.text(title, 42, 16, -1, 2)


def draw_waiting(text, detail=None):
    display.set_pen(MUTED)
    display.text(text, 12, 60, WIDTH - 24, 2)
    if detail:
        display.text(detail, 12, 100, -1, 1)


def shorten(text, n):
    """Cut at a word boundary and mark it with '..'."""
    if len(text) <= n:
        return text
    cut = text[:n - 2]
    if " " in cut[n // 2:]:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" :-,") + ".."


def tick_if(cond, now, ms):
    """A number that changes every ms milliseconds while cond holds."""
    return now // ms if cond else 0


# --- today: the daily note ------------------------------------------------------

CALENDAR = ("#.#.#", "#####", "#...#", "#.#.#", "#####")
OFFICE = ("#####", "#.#.#", "#####", "#.#.#", "#####")
ROW = 12


def today_key(now):
    t = seasons.today(now)
    return herdr.day, (t[3] * 60 + t[4]) if t else 0  # the next appointment moves on


def draw_today(now):
    day = herdr.day
    draw_header(CALENDAR, 10, 9, ALERT_PEN, "HEUTE")
    bottom = BOTTOM
    if not day:
        draw_waiting("Waiting for the daily note...", "comes with the pipeline poller")
        return
    _, mo, d = day["date"].split("-")
    date = "%d.%d." % (int(d), int(mo))
    display.set_pen(MUTED)
    display.text(date, WIDTH - 12 - display.measure_text(date, 2), 16, -1, 2)
    if not day.get("note"):
        draw_waiting("Kein Arbeitstag", "Keine Tagesnotiz fuer heute")
        return
    t = seasons.today(now)
    nxt = herdr.next_event(t)
    y = 34
    place = day.get("place")
    if place:  # home office or the office
        colour = TICK_PEN if place == "home" else pen((255, 163, 0))
        draw_art(HOUSE if place == "home" else OFFICE, 10, y, 2, colour)
        display.set_pen(colour)
        display.text("HOMEOFFICE" if place == "home" else "BUERO", 24, y + 1, -1, 1)
        y += 14
    if day["events"]:
        y = draw_label("TERMINE", y)
        for e in day["events"]:
            if y + ROW > bottom:
                return
            if e is nxt:
                draw_panel(6, y - 2, WIDTH - 12, ROW + 2)
            past = not e.get("x") and nxt is not None and e is not nxt and e["t"] < nxt["t"]
            display.set_pen(MUTED if e.get("x") or past else TEXT_PEN)
            display.text(e["t"], 14, y, -1, 1)
            display.text(shorten(e["n"], (WIDTH - 60) // 6), 50, y, -1, 1)
            if e.get("x"):  # crossed out
                display.rectangle(50, y + 3, display.measure_text(shorten(e["n"], (WIDTH - 60) // 6), 1), 1)
            y += ROW
        y += 4
    if day["tasks"]:
        y = draw_label("AUFGABEN", y)
        for i, task in enumerate(day["tasks"]):
            if y + ROW > bottom:
                display.set_pen(MUTED)
                display.text("+%d" % (len(day["tasks"]) - i), WIDTH - 30, y - ROW, -1, 1)
                return
            done = task.get("x")
            draw_checkbox(14, y, done)
            display.set_pen(MUTED if done else TEXT_PEN)
            display.text(shorten(task["n"], (WIDTH - 34) // 6), 26, y, -1, 1)
            y += ROW


def draw_label(text, y):
    display.set_pen(MUTED)
    display.text(text, 10, y, -1, 1)
    w = display.measure_text(text, 1)
    display.rectangle(14 + w, y + 3, WIDTH - 24 - w, 1)
    return y + 12


def draw_checkbox(x, y, done):
    if done:
        display.set_pen(TICK_PEN)
        display.rectangle(x, y, 7, 7)
    else:
        display.set_pen(MUTED)
        display.rectangle(x, y, 7, 1)
        display.rectangle(x, y + 6, 7, 1)
        display.rectangle(x, y, 1, 7)
        display.rectangle(x + 6, y, 1, 7)


# --- agents ------------------------------------------------------------------
# herdr sorts the agents: waiting for you, working, done, idle. While they all
# fit they get a full row each. When it gets crowded the idle ones share one
# line at the bottom, then the rows shrink to one line, and what still doesn't
# fit is counted in a last line. Claude's limits sit in a slim tile below.

STATUS_PEN = {"working": CLAWD_PEN, "blocked": ALERT_PEN, "done": TICK_PEN, "idle": IDLE_PEN}
ACTIVE = ("blocked", "working", "done")
FULL_ROW = 38  # two lines: workspace, then kind and title
SMALL_ROW = 22  # one line: workspace and status
LINE = 14  # the idle line and the "+N" line
USAGE_H = 20


def agents_key(now):
    agents = herdr.agent_list
    if not agents:
        return wlan.isconnected(), herdr.usage
    return (agents, herdr.usage,
            tick_if(any(a.get("s") == "working" for a in agents), now, 150),
            tick_if(any(a.get("s") == "blocked" for a in agents), now, 400))


def agent_layout(agents, height):
    """(row height, agents in rows, idle ones for the shared line, rest)."""
    if len(agents) * FULL_ROW <= height:
        return FULL_ROW, agents, [], []
    active = [a for a in agents if a.get("s") in ACTIVE]
    idle = [a for a in agents if a.get("s") not in ACTIVE]
    room = height - (LINE if idle else 0)
    if len(active) * FULL_ROW <= room:
        return FULL_ROW, active, idle, []
    if len(active) * SMALL_ROW <= room:
        return SMALL_ROW, active, idle, []
    n = max(0, (room - LINE) // SMALL_ROW)
    return SMALL_ROW, active[:n], idle, active[n:]


def draw_agent_icon(status, x, y, s, now, blink, colour):
    if status == "working":
        draw_art(SPARK if (now // 150) % 2 else SPARK_X, x + s // 3, y + s // 3, s + s // 3, colour)
    elif status == "blocked":
        if blink:
            draw_art(EXCL, x, y - s * 2 // 3, s, colour)
    elif status == "done":
        draw_art(TICK, x, y, s, colour)
    elif status == "idle":
        draw_art(RING, x, y, s, colour)
    else:
        draw_art(QMARK, x, y - s * 2 // 3, s, colour)


def draw_agent_row(a, y, h, now, blink):
    status = a.get("s", "unknown")
    colour = STATUS_PEN.get(status, MUTED)
    draw_panel(6, y, WIDTH - 12, h - 2, ALERT_PEN if status == "blocked" and blink else None)
    display.set_pen(colour)
    display.rectangle(9, y + 3, 3, h - 8)
    word = status.upper()
    ww = display.measure_text(word, 1)
    if h == FULL_ROW:  # line 1: workspace and status, line 2: agent kind and terminal title
        draw_agent_icon(status, 17, y + 10, 3, now, blink, colour)
        display.set_pen(TEXT_PEN)
        display.text(a.get("w", "")[:(WIDTH - 60 - ww) // 12], 38, y + 6, -1, 2)
        line = a.get("k", "")
        if a.get("t"):
            line = line + " - " + a["t"] if line else a["t"]
        display.set_pen(MUTED)
        display.text(line[:(WIDTH - 52) // 6], 38, y + 24, -1, 1)
        ty = y + 10
    else:
        draw_agent_icon(status, 17, y + 5, 2, now, blink, colour)
        display.set_pen(TEXT_PEN)
        display.text(a.get("w", "")[:(WIDTH - 52 - ww) // 12], 34, y + 3, -1, 2)
        ty = y + 7
    display.set_pen(colour if status != "blocked" or blink else MUTED)
    display.text(word, WIDTH - 14 - ww, ty, -1, 1)


def draw_agents(now):
    agents = herdr.agent_list
    draw_header(MINI_CLAWD, 10, 8, CLAWD_PEN, "AGENTS")
    bottom = BOTTOM
    if herdr.usage:
        bottom -= USAGE_H + 2
        draw_usage(herdr.usage, bottom + 2)
    if not agents:
        draw_waiting("Waiting for Herdr...", wlan.ifconfig()[0] if wlan.isconnected() else "no WiFi yet")
        return
    n = str(len(agents))
    display.set_pen(MUTED)
    display.text(n, WIDTH - 12 - display.measure_text(n, 2), 16, -1, 2)
    blink = (now // 400) % 2 == 0
    h, rows, idle, rest = agent_layout(agents, bottom - 34)
    y = 34
    for a in rows:
        draw_agent_row(a, y, h, now, blink)
        y += h
    if rest:  # what doesn't fit, counted by status
        counts = []
        for s in ACTIVE:
            c = sum(1 for a in rest if a.get("s") == s)
            if c:
                counts.append("%d %s" % (c, s))
        display.set_pen(TEXT_PEN)
        display.text(shorten("+ " + ", ".join(counts), (WIDTH - 24) // 6), 12, y + 3, -1, 1)
        y += LINE
    if idle:  # the idle ones share a line
        names = ", ".join(a.get("w", "?") for a in idle)
        draw_art(RING_SMALL, 12, y + 3, 2, IDLE_PEN)
        display.set_pen(MUTED)
        display.text(shorten("%d idle: %s" % (len(idle), names), (WIDTH - 34) // 6), 22, y + 3, -1, 1)


def usage_pen(p):
    return TICK_PEN if p < 50 else ALERT_PEN if p < 80 else FAIL_PEN


def draw_usage(usage, y):
    """Claude's limits in a slim tile: the 5 hour window and the week, each a
    chunky bar with the percentage and when it resets (the week: the day)."""
    draw_panel(6, y, WIDTH - 12, USAGE_H)
    col = (WIDTH - 12) // 2
    for i, (key, label) in enumerate((("5h", "5H"), ("7d", "7D"))):
        w = usage.get(key)
        if not w:
            continue
        x, p = 12 + i * col, min(100, max(0, w["p"]))
        display.set_pen(MUTED)
        display.text(label, x, y + 7, -1, 1)
        x += display.measure_text(label, 1) + 4
        display.set_pen(BG)
        display.rectangle(x, y + 4, 32, 12)
        display.set_pen(usage_pen(p))
        display.rectangle(x, y + 4, (32 * p // 100 + 2) // 4 * 4, 12)
        x += 36
        word = "%d%%" % p
        display.text(word, x, y + 7, -1, 1)
        if w.get("r"):
            display.set_pen(MUTED)
            r = w["r"].split(" ")[0] if key == "7d" else w["r"]  # the week: just the day
            display.text(r, x + display.measure_text(word, 1) + 4, y + 7, -1, 1)


# --- pipelines -----------------------------------------------------------------

PIPE_PEN = {"running": FUR_PEN, "pending": WHEEL_PEN, "created": WHEEL_PEN, "failed": FAIL_PEN,
            "success": TICK_PEN, "manual": MANUAL_PEN}
PIPE_WORD = {"running": "RUNNING", "pending": "QUEUED", "created": "QUEUED", "scheduled": "QUEUED",
             "waiting_for_resource": "QUEUED", "preparing": "QUEUED", "failed": "FAILED",
             "success": "PASSED", "manual": "MANUAL", "canceled": "CANCELED", "skipped": "SKIPPED"}
WAITING = ("pending", "created", "scheduled", "waiting_for_resource", "preparing")


def pipelines_key(now):
    items = herdr.pipe_items
    if not items:
        return herdr.pipes_fresh(now)
    return (items,
            tick_if(any(it.get("s") == "running" for it in items), now, 200),
            tick_if(any(it.get("s") == "failed" for it in items), now, 400))


def pipe_icon(st, x, y, colour, now):
    if st == "running":
        draw_art(GEAR_A if (now // 200) % 2 else GEAR_B, x, y, 3, colour)
    elif st == "failed":
        draw_art(CROSS, x, y, 3, colour)
    elif st == "success":
        draw_art(TICK, x, y, 3, colour)
    elif st == "manual":
        draw_art(PLAY, x + 2, y, 3, colour)
    elif st in WAITING:
        draw_art(CLOCK, x, y, 3, colour)
    else:
        draw_art(SLASH, x, y, 3, colour)


QUIET = ("success", "canceled", "skipped")  # nothing to do: share a line when it's crowded
PIPE_ROW = 34
PIPE_SMALL = 22
PIPE_HEAD = 11  # space name above its rows
SMALL_ICON = {"failed": CROSS, "success": TICK, "manual": PLAY}


def pipe_layout(rows, spaces, height):
    """(row height, rows to draw, quiet ones for the shared line, rest)."""
    heads = PIPE_HEAD * len(spaces) if len(spaces) > 1 else 0
    if len(rows) * PIPE_ROW + heads <= height:
        return PIPE_ROW, rows, [], []
    busy = [it for it in rows if it.get("s") not in QUIET]
    quiet = [it for it in rows if it.get("s") in QUIET]
    room = height - (LINE if quiet else 0)
    busy_spaces = len(set(it.get("w", "") for it in busy))
    if len(busy) * PIPE_ROW + (PIPE_HEAD * busy_spaces if len(spaces) > 1 else 0) <= room:
        return PIPE_ROW, busy, quiet, []
    if len(busy) * PIPE_SMALL <= room:
        return PIPE_SMALL, busy, quiet, []
    n = max(0, (room - LINE) // PIPE_SMALL)
    return PIPE_SMALL, busy[:n], quiet, busy[n:]


def draw_pipe_row(it, y, now, blink):
    st = it.get("s", "")
    colour = PIPE_PEN.get(st, IDLE_PEN)
    draw_panel(6, y, WIDTH - 12, 32, FAIL_PEN if st == "failed" and blink else None)
    display.set_pen(colour)
    display.rectangle(9, y + 3, 3, 26)
    pipe_icon(st, 17, y + 8, colour, now)
    # right: status word, below it progress + duration (running) or age
    word = PIPE_WORD.get(st, st.upper()[:8])
    ww = display.measure_text(word, 1)
    display.set_pen(colour)
    display.text(word, WIDTH - 14 - ww, y + 5, -1, 1)
    if st == "running" or st in WAITING:
        info = " ".join(v for v in (it.get("p"), it.get("d")) if v)
    else:
        info = it["a"] + " ago" if it.get("a") else ""
    iw = display.measure_text(info, 1)
    display.set_pen(MUTED)
    display.text(info, WIDTH - 14 - iw, y + 14, -1, 1)
    # left: MR / branch big, the title (or the failed job) below
    display.set_pen(TEXT_PEN)
    display.text(shorten(it.get("n", ""), (WIDTH - 62 - max(ww, iw)) // 12), 38, y + 5, -1, 2)
    if it.get("f"):
        display.set_pen(FAIL_PEN)
        line = "failed: " + it["f"]
    else:
        display.set_pen(MUTED)
        line = it.get("t", "")
    display.text(shorten(line, (WIDTH - 52) // 6), 38, y + 22, -1, 1)


def draw_pipe_small(it, y, now, blink, with_space):
    """One line: icon, MR or branch, the space, status (or progress)."""
    st = it.get("s", "")
    colour = PIPE_PEN.get(st, IDLE_PEN)
    draw_panel(6, y, WIDTH - 12, PIPE_SMALL - 2, FAIL_PEN if st == "failed" and blink else None)
    display.set_pen(colour)
    display.rectangle(9, y + 3, 3, PIPE_SMALL - 8)
    if st == "running":
        art = GEAR_A if (now // 200) % 2 else GEAR_B
    else:
        art = SMALL_ICON.get(st, CLOCK if st in WAITING else SLASH)
    draw_art(art, 16, y + 5, 2, colour)
    word = it.get("p") if st == "running" and it.get("p") else PIPE_WORD.get(st, st.upper()[:8])
    ww = display.measure_text(word, 1)
    display.set_pen(colour)
    display.text(word, WIDTH - 14 - ww, y + 7, -1, 1)
    name = it.get("n", "")
    display.set_pen(TEXT_PEN)
    display.text(shorten(name, (WIDTH - 52 - ww) // 12), 32, y + 3, -1, 2)
    if with_space:
        x = 36 + display.measure_text(shorten(name, (WIDTH - 52 - ww) // 12), 2)
        room = (WIDTH - 20 - ww - x) // 6
        if room >= 3:
            display.set_pen(MUTED)
            display.text(shorten(it.get("w", ""), room), x, y + 7, -1, 1)


def draw_pipelines(now):
    items = herdr.pipe_items
    draw_header(MINI_HAMSTER, 10, 9, FUR_PEN, "PIPELINES")
    if not items:
        if herdr.pipes_fresh(now):
            draw_waiting("All quiet: no pipelines in your spaces")
        else:
            draw_waiting("Waiting for GitLab...", "Herdr plugin: pipelines-start")
        return
    # Group rows by space (keeping the urgency order inside); with a single
    # space its name goes into the header instead. When they don't all fit,
    # the passed ones share a line, the others get one line each (with their
    # space), and what still doesn't fit is counted.
    spaces = []
    for it in items:
        if it.get("w", "") not in spaces:
            spaces.append(it.get("w", ""))
    rows = [it for sp in spaces for it in items if it.get("w", "") == sp]
    if len(spaces) == 1 and spaces[0]:
        display.set_pen(MUTED)
        label = shorten(spaces[0], 7)
        display.text(label, WIDTH - 12 - display.measure_text(label, 1), 20, -1, 1)
    blink = (now // 400) % 2 == 0
    y = 32
    h, shown, quiet, rest = pipe_layout(rows, spaces, BOTTOM - y)
    last_space = None
    for it in shown:
        if h == PIPE_ROW:
            if len(spaces) > 1 and it.get("w", "") != last_space:
                last_space = it.get("w", "")
                label = last_space.upper()
                lw = display.measure_text(label, 1)
                display.set_pen(MUTED)
                display.text(label, 10, y + 1, -1, 1)
                display.rectangle(14 + lw, y + 4, WIDTH - 28 - lw, 1)
                y += PIPE_HEAD
            draw_pipe_row(it, y, now, blink)
        else:
            draw_pipe_small(it, y, now, blink, len(spaces) > 1)
        y += h
    if rest:
        counts = {}
        for it in rest:
            word = PIPE_WORD.get(it.get("s", ""), "OTHER").lower()
            counts[word] = counts.get(word, 0) + 1
        display.set_pen(TEXT_PEN)
        display.text(shorten("+ " + ", ".join("%d %s" % (n, w) for w, n in counts.items()), (WIDTH - 24) // 6),
                     12, y + 3, -1, 1)
        y += LINE
    if quiet:
        draw_art(TICK, 10, y + 1, 2, TICK_PEN)
        display.set_pen(MUTED)
        names = ", ".join(it.get("n", "") for it in quiet)
        word = "passed" if all(it.get("s") == "success" for it in quiet) else "finished"
        display.text(shorten("%d %s: %s" % (len(quiet), word, names), (WIDTH - 36) // 6), 24, y + 3, -1, 1)


# --- home ----------------------------------------------------------------------

def draw_climate(bottom):
    values = climate.values if climate else None
    if values is None:
        return bottom
    y = bottom - 40
    draw_panel(6, y, WIDTH - 12, 36)
    display.set_pen(MUTED)
    display.text("RAUMKLIMA", 14, y + 5, -1, 1)
    temperature, humidity, pressure = values
    draw_degrees("%.1f" % temperature, 14, y + 17, 2, TEXT_PEN)
    display.set_pen(TEXT_PEN)
    display.text("%d%%" % humidity, 108, y + 17, -1, 2)
    display.text("%d hPa" % pressure, 168, y + 21, -1, 1)
    return y - 4


def home_key(now):
    return (ha.version(), tick_if(ha.low_batteries(), now, 500),
            climate.values if climate else None)


def draw_home(now):
    person = ha.person_state()
    at_home = person and person["state"] == "home"
    draw_header(HOUSE, 10, 9, TICK_PEN if at_home else IDLE_PEN, "HOME")
    low = ha.low_batteries()
    bottom = draw_climate(216 if low else BOTTOM)
    if not ha.HA_TOKEN or not ha.ready():
        draw_waiting("Waiting for Home Assistant...")
        return
    if person:
        word = "DA" if at_home else "UNTERWEGS"
        display.set_pen(TICK_PEN if at_home else MUTED)
        display.text(word, WIDTH - 12 - display.measure_text(word, 1), 20, -1, 1)
    draw_weather_tile()
    draw_rooms(bottom)
    # low batteries, one at a time
    if low:
        text = "BATTERIE " + low[(now // 3000) % len(low)]
        display.set_pen(FAIL_PEN if (now // 500) % 2 else MUTED)
        display.text(text[:38], 10, 218, -1, 1)


def draw_weather_tile():
    cond, night = ha.weather()
    w = ha.weather_state()
    draw_panel(6, 32, WIDTH - 12, 46)
    draw_weather_icon(cond, night, 18, 41, 4)
    if not w:
        return
    a = w["attributes"]
    if a.get("temperature") is not None:
        draw_degrees("%d" % round(a["temperature"]), 82, 42, 4, TEXT_PEN)
    display.set_pen(TEXT_PEN)
    desc = ha.CONDITION_DE.get(cond, (cond or "").upper())
    display.text(desc, WIDTH - 14 - display.measure_text(desc, 1), 44, -1, 1)
    info = []
    if a.get("humidity") is not None:
        info.append("%d%%" % round(a["humidity"]))
    if a.get("wind_speed") is not None:
        info.append("%d km/h" % round(a["wind_speed"]))
    info = "  ".join(info)
    display.set_pen(MUTED)
    display.text(info, WIDTH - 14 - display.measure_text(info, 1), 58, -1, 1)


def draw_rooms(bottom):
    """Per room: light bulb, name, temperature and a flame while heating."""
    y = 84
    rooms = ha.HAC.ROOMS
    compact = len(rooms) * 19 > bottom - y
    row, scale, icon_scale = (14, 1, 2) if compact else (19, 2, 3)
    capacity = max(0, (bottom - y) // row)
    shown = capacity - 1 if len(rooms) > capacity else len(rooms)
    for label, temp_id, light_id in rooms[:max(0, shown)]:
        light = ha.state(light_id)
        on = light and light["state"] == "on"
        draw_art(BULB, 12, y + 2, icon_scale, ALERT_PEN if on else BULB_OFF_PEN)
        display.set_pen(TEXT_PEN if on else MUTED)
        display.text(shorten(label, 21 if compact else 10), 28 if compact else 34, y + 2, -1, scale)
        st = ha.state(temp_id)
        if st:
            a = st["attributes"]
            value = a.get("current_temperature") if temp_id.startswith("climate.") else st["state"]
            try:
                text = "%.1f" % float(value)
            except (TypeError, ValueError):
                text = "--"
            tw = display.measure_text(text, scale) + 10
            draw_degrees(text, WIDTH - 14 - tw, y + 2, scale, TEXT_PEN)
            if a.get("hvac_action") == "heating":
                draw_art(FLAME, WIDTH - 32 - tw, y + 2, icon_scale, FLAME_PEN)
        y += row
    if len(rooms) > capacity and capacity:
        display.set_pen(MUTED)
        display.text("+%d weitere Raeume" % (len(rooms) - max(0, shown)), 12, y + 2, -1, 1)


# --- settings ------------------------------------------------------------------

SETTING_ROWS = (("leds", "LEDS", "Status: Claude, pipelines"), ("anim_leds", "ANIM LIGHTS", "Moods, party, fight"),
                ("sounds", "SOUNDS", "Pipelines and Claude"), ("anim", "ANIMATION", "Sounds of the scenes"),
                ("music", "MUSIC", "Guybrush and dance songs"))
SETTING_Y0, SETTING_H = 32, 38


def settings_key(now):
    return tuple(prefs.settings[key] for key, _, _ in SETTING_ROWS), pad_focus


def draw_settings(now):
    draw_header(GEAR, 12, 9, MANUAL_PEN, "SETTINGS")
    for i, (key, label, hint) in enumerate(SETTING_ROWS):
        y = SETTING_Y0 + i * SETTING_H
        on = prefs.settings[key]
        draw_panel(6, y, WIDTH - 12, SETTING_H - 4,
                   TEXT_PEN if pad_focus == ("settings", i) else None)
        display.set_pen(TEXT_PEN if on else MUTED)
        display.text(label, 16, y + 5, -1, 2)
        display.set_pen(MUTED)
        display.text(hint, 16, y + 23, -1, 1)
        # pixel toggle switch: knob right and green when on
        sx, sy = WIDTH - 62, y + 7
        display.set_pen(SHADE)
        display.rectangle(sx, sy, 44, 20)
        display.set_pen(TICK_PEN if on else IDLE_PEN)
        display.rectangle(sx + 2, sy + 2, 40, 16)
        display.set_pen(TEXT_PEN)
        display.rectangle(sx + (24 if on else 4), sy + 4, 14, 12)


def tap_settings(tx, ty):
    i = (ty - SETTING_Y0) // SETTING_H
    if 0 <= i < len(SETTING_ROWS) and ty >= SETTING_Y0:
        key = SETTING_ROWS[i][0]
        prefs.settings[key] = not prefs.settings[key]
        prefs.save()
        if key == "sounds" and prefs.settings[key]:
            sound.play("click")


# --- apps ------------------------------------------------------------------------
# 3 x 4 tiles, one per app (desk/apps.py). A tap lights the tile up, then the
# Presto resets into the app.

APP_COLS, APP_W, APP_H, APP_GX, APP_GY, APP_Y0 = 3, 72, 44, 8, 4, 36
APP_X0 = (WIDTH - (APP_COLS * APP_W + (APP_COLS - 1) * APP_GX)) // 2
_starting = None  # index of the app being started


def app_slot(i):
    return APP_X0 + (i % APP_COLS) * (APP_W + APP_GX), APP_Y0 + (i // APP_COLS) * (APP_H + APP_GY)


def apps_key(now):
    return _starting, pad_focus


def draw_apps(now):
    from desk import apps  # only now: compiling its icons at boot costs ~200 ms

    draw_header(GRID, 12, 9, MANUAL_PEN, "APPS")
    found = apps.get()
    if not found:
        draw_waiting("NO APPS")
        return
    for i, (_, label, art, pens) in enumerate(found):
        x, y = app_slot(i)
        draw_panel(x, y, APP_W, APP_H,
                   TEXT_PEN if i == _starting or pad_focus == ("apps", i) else None)
        draw_colour_art(art, pens, x + (APP_W - 24) // 2, y + 4, 2)
        display.set_pen(TEXT_PEN)
        display.text(label, x + (APP_W - display.measure_text(label, 1)) // 2, y + 32, -1, 1)


def tap_apps(tx, ty, now):
    from desk import apps

    global _starting
    found = apps.get()
    for i in range(len(found)):
        x, y = app_slot(i)
        if x <= tx < x + APP_W and y <= ty < y + APP_H:
            _starting = i
            if show("apps", now):
                presto.update()
            apps.launch(found[i][0])


# --- showing a page --------------------------------------------------------------

PAGES = {  # view -> (key, draw)
    "today": (today_key, draw_today),
    "agents": (agents_key, draw_agents),
    "pipelines": (pipelines_key, draw_pipelines),
    "home": (home_key, draw_home),
    "settings": (settings_key, draw_settings),
    "apps": (apps_key, draw_apps),
}
_shown = None  # (view, key) on screen right now


def show(view, now):
    """Draw the page if it changed; returns whether it did."""
    global _shown
    key_of, draw = PAGES[view]
    global _now
    scene.update_sky_colours(now)
    lights = garland_kind(now) == "lights"
    key = (view, key_of(now), scene.sky_colour, now // 700 if lights else 0)
    if key == _shown:
        return False
    _now = now
    set_theme(scene.sky_colour)
    draw(now)
    draw_page_dots(view)
    _shown = key
    return True


def forget():
    """The scene drew over the screen: draw the next page in full again."""
    global _shown
    _shown = None
