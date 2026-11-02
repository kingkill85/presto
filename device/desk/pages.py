# The pages next to the scene: today, agents, pipelines, home, settings and apps.
#
# They hardly move, so each one is only drawn (and sent to the screen) again
# when its key changes: the data it shows plus a clock tick for every blink or
# spinner that is visible right now. That saves ~20 ms per frame.

import network

from desk import apps, prefs, sound
from desk.data import ha, herdr
from desk.gfx import (ALERT_PEN, CLAWD_PEN, CLOCK, CROSS, DIM_PEN, EXCL, FAIL_PEN, FUR_PEN, GEAR_A,
                       GEAR_B, HEIGHT, IDLE_PEN, MANUAL_PEN, PLAY, QMARK, RING,
                       SLASH, SPARK, SPARK_X, TEXT_PEN, TICK, TICK_PEN, WHEEL_PEN, WIDTH, display, draw_art,
                       draw_colour_art, draw_degrees, pen, presto)
from desk.scene import scene, seasons
from desk.scene.scene import draw_weather_icon

wlan = network.WLAN(network.STA_IF)
VIEWS = ("scene", "today", "agents", "pipelines", "home", "settings", "apps")  # swipe order

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


# Garlands, 4 px pixel art repeated every 16 px under a string; x takes the
# colour that alternates along it
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
    display.set_pen(MUTED)  # the string
    display.rectangle(0, 0, WIDTH, 2)
    step = (now // 700) if kind == "lights" else 0  # the lights take turns
    for i, bx in enumerate(range(2, WIDTH, 16)):
        rows = art[:ICICLES[i % len(ICICLES)]] if kind == "winter" else art
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == ".":
                    continue
                display.set_pen(colours[(i + step) % len(colours)] if ch == "x" else second)
                display.rectangle(bx + c * 4, 2 + r * 4, 4, 4)


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
            if y + ROW > BOTTOM:
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
            if y + ROW > BOTTOM:
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

STATUS_PEN = {"working": CLAWD_PEN, "blocked": ALERT_PEN, "done": TICK_PEN, "idle": IDLE_PEN}
MAX_AGENTS = 5


def agents_key(now):
    agents = herdr.agent_list
    if not agents:
        return wlan.isconnected()
    shown = agents[:MAX_AGENTS]
    return (agents,
            tick_if(any(a.get("s") == "working" for a in shown), now, 150),
            tick_if(any(a.get("s") == "blocked" for a in shown), now, 400))


def draw_agents(now):
    agents = herdr.agent_list
    draw_header(MINI_CLAWD, 10, 8, CLAWD_PEN, "AGENTS")
    if not agents:
        draw_waiting("Waiting for Herdr...", wlan.ifconfig()[0] if wlan.isconnected() else "no WiFi yet")
        return
    n = str(len(agents))
    display.set_pen(MUTED)
    display.text(n, WIDTH - 12 - display.measure_text(n, 2), 16, -1, 2)
    blink = (now // 400) % 2 == 0
    for i, a in enumerate(agents[:MAX_AGENTS]):
        y = 34 + i * 38
        status = a.get("s", "unknown")
        colour = STATUS_PEN.get(status, MUTED)
        draw_panel(6, y, WIDTH - 12, 36, ALERT_PEN if status == "blocked" and blink else None)
        # status stripe and icon on the left
        display.set_pen(colour)
        display.rectangle(9, y + 3, 3, 30)
        ix, iy = 17, y + 10
        if status == "working":
            draw_art(SPARK if (now // 150) % 2 else SPARK_X, ix + 1, iy + 1, 4, colour)
        elif status == "blocked":
            if blink:
                draw_art(EXCL, ix, iy - 2, 3, colour)
        elif status == "done":
            draw_art(TICK, ix, iy, 3, colour)
        elif status == "idle":
            draw_art(RING, ix, iy, 3, colour)
        else:
            draw_art(QMARK, ix, iy - 2, 3, colour)
        # line 1: workspace and status, line 2: agent kind and terminal title
        word = status.upper()
        ww = display.measure_text(word, 1)
        display.set_pen(TEXT_PEN)
        display.text(a.get("w", "")[:(WIDTH - 60 - ww) // 12], 38, y + 6, -1, 2)
        display.set_pen(colour if status != "blocked" or blink else MUTED)
        display.text(word, WIDTH - 14 - ww, y + 10, -1, 1)
        line = a.get("k", "")
        if a.get("t"):
            line = line + " - " + a["t"] if line else a["t"]
        display.set_pen(MUTED)
        display.text(line[:(WIDTH - 52) // 6], 38, y + 24, -1, 1)


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
    # space its name goes into the header instead
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
    y, last_space = 32, None
    for it in rows:
        if len(spaces) > 1 and it.get("w", "") != last_space:
            if y + 46 > HEIGHT - 10:
                break
            last_space = it.get("w", "")
            label = last_space.upper()
            lw = display.measure_text(label, 1)
            display.set_pen(MUTED)
            display.text(label, 10, y + 1, -1, 1)
            display.rectangle(14 + lw, y + 4, WIDTH - 28 - lw, 1)
            y += 11
        if y + 34 > HEIGHT - 10:
            break
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
        y += 34


# --- home ----------------------------------------------------------------------

def home_key(now):
    return ha.version(), tick_if(ha.low_batteries(), now, 500)


def draw_home(now):
    person = ha.person_state()
    at_home = person and person["state"] == "home"
    draw_header(HOUSE, 10, 9, TICK_PEN if at_home else IDLE_PEN, "HOME")
    if not ha.HA_TOKEN or not ha.ready():
        draw_waiting("Waiting for Home Assistant...")
        return
    if person:
        word = "DA" if at_home else "UNTERWEGS"
        display.set_pen(TICK_PEN if at_home else MUTED)
        display.text(word, WIDTH - 12 - display.measure_text(word, 1), 20, -1, 1)
    draw_weather_tile()
    draw_rooms()
    # low batteries, one at a time
    low = ha.low_batteries()
    if low:
        text = "BATTERIE " + low[(now // 3000) % len(low)]
        display.set_pen(FAIL_PEN if (now // 500) % 2 else MUTED)
        display.text(text[:38], 10, 218, -1, 1)


def draw_weather_tile():
    cond, night = ha.weather()
    w = ha.weather_state()
    draw_panel(6, 32, WIDTH - 12, 58)
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


def draw_rooms():
    """Per room: light bulb, name, temperature and a flame while heating."""
    y = 96
    for label, temp_id, light_id in ha.HAC.ROOMS:
        light = ha.state(light_id)
        on = light and light["state"] == "on"
        draw_art(BULB, 12, y + 2, 3, ALERT_PEN if on else BULB_OFF_PEN)
        display.set_pen(TEXT_PEN if on else MUTED)
        display.text(label, 34, y + 2, -1, 2)
        st = ha.state(temp_id)
        if st:
            a = st["attributes"]
            value = a.get("current_temperature") if temp_id.startswith("climate.") else st["state"]
            try:
                text = "%.1f" % float(value)
            except (TypeError, ValueError):
                text = "--"
            tw = display.measure_text(text, 2) + 10
            draw_degrees(text, WIDTH - 14 - tw, y + 2, 2, TEXT_PEN)
            if a.get("hvac_action") == "heating":
                draw_art(FLAME, WIDTH - 32 - tw, y + 2, 3, FLAME_PEN)
        y += 19


# --- settings ------------------------------------------------------------------

SETTING_ROWS = (("leds", "LEDS", "Status: Claude, pipelines"), ("anim_leds", "ANIM LIGHTS", "Moods, party, fight"),
                ("sounds", "SOUNDS", "Pipelines and Claude"), ("anim", "ANIMATION", "Sounds of the scenes"),
                ("music", "MUSIC", "Guybrush and dance songs"))
SETTING_Y0, SETTING_H = 32, 38


def settings_key(now):
    return tuple(prefs.settings[key] for key, _, _ in SETTING_ROWS)


def draw_settings(now):
    draw_header(GEAR, 12, 9, MANUAL_PEN, "SETTINGS")
    for i, (key, label, hint) in enumerate(SETTING_ROWS):
        y = SETTING_Y0 + i * SETTING_H
        on = prefs.settings[key]
        draw_panel(6, y, WIDTH - 12, SETTING_H - 4)
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
    return _starting


def draw_apps(now):
    draw_header(GRID, 12, 9, MANUAL_PEN, "APPS")
    if not apps.apps:
        draw_waiting("NO APPS")
        return
    for i, (_, label, art, pens) in enumerate(apps.apps):
        x, y = app_slot(i)
        draw_panel(x, y, APP_W, APP_H, TEXT_PEN if i == _starting else None)
        draw_colour_art(art, pens, x + (APP_W - 24) // 2, y + 4, 2)
        display.set_pen(TEXT_PEN)
        display.text(label, x + (APP_W - display.measure_text(label, 1)) // 2, y + 32, -1, 1)


def tap_apps(tx, ty, now):
    global _starting
    for i in range(len(apps.apps)):
        x, y = app_slot(i)
        if x <= tx < x + APP_W and y <= ty < y + APP_H:
            _starting = i
            if show("apps", now):
                presto.update()
            apps.launch(apps.apps[i][0])


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
