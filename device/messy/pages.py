# The pages next to the scene: agents, pipelines, home and settings.
#
# They hardly move, so each one is only drawn (and sent to the screen) again
# when its key changes: the data it shows plus a clock tick for every blink or
# spinner that is visible right now. That saves ~20 ms per frame.

import network

from messy import herdr, home, prefs, seasons, sound
from messy.gfx import (ALERT_PEN, BACKGROUND, CLAWD_PEN, CLOCK, CROSS, DIM_PEN, EXCL, FAIL_PEN, FUR_PEN, GEAR_A,
                       GEAR_B, HEIGHT, IDLE_PEN, MANUAL_PEN, PANEL_HI_PEN, PANEL_LO_PEN, PANEL_PEN, PLAY, QMARK, RING,
                       SLASH, SPARK, SPARK_X, TEXT_PEN, TICK, TICK_PEN, WHEEL_PEN, WIDTH, display, draw_art,
                       draw_degrees, pen)
from messy.scene import draw_weather_icon

wlan = network.WLAN(network.STA_IF)
VIEWS = ("scene", "today", "agents", "pipelines", "home", "settings")  # swipe order

MINI_HAMSTER = (".#....#.", "########", "##.##.##", "########", ".######.")
MINI_CLAWD = (".######.", ".#.##.#.", "########", ".######.", ".#.#.#.#")
HOUSE = ("..#..", ".###.", "#####", "#.#.#", "#.#.#")
GEAR = (".#.#.", "#####", "##.##", "#####", ".#.#.")
FLAME = ("..#..", ".##..", ".###.", "#####", ".###.")
BULB = (".###.", "#####", "#####", ".###.", ".#.#.")
FLAME_PEN = pen((255, 120, 30))
BULB_OFF_PEN = pen((70, 70, 90))


def draw_page_dots(view):
    i0 = VIEWS.index(view)
    x0 = WIDTH // 2 - (len(VIEWS) * 12 - 6) // 2
    for i in range(len(VIEWS)):
        display.set_pen(TEXT_PEN if i == i0 else DIM_PEN)
        display.rectangle(x0 + i * 12, HEIGHT - 8, 6, 6)


def draw_panel(x, y, w, h, hi=None):
    """Bevelled pixel tile: light top/left edge, dark bottom/right edge."""
    display.set_pen(PANEL_LO_PEN)
    display.rectangle(x, y, w, h)
    display.set_pen(hi or PANEL_HI_PEN)
    display.rectangle(x, y, w - 3, h - 3)
    display.set_pen(PANEL_PEN)
    display.rectangle(x + 3, y + 3, w - 6, h - 6)


def draw_header(art, x, y, colour, title):
    display.set_pen(BACKGROUND)
    display.clear()
    draw_art(art, x, y, 3, colour)
    display.set_pen(TEXT_PEN)
    display.text(title, 42, 10, -1, 2)


def draw_waiting(text, detail=None):
    display.set_pen(DIM_PEN)
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
ROW = 12
BOTTOM = HEIGHT - 12  # above the page dots


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
    display.set_pen(DIM_PEN)
    display.text(date, WIDTH - 12 - display.measure_text(date, 2), 10, -1, 2)
    if not day.get("note"):
        draw_waiting("Kein Arbeitstag", "Keine Tagesnotiz fuer heute")
        return
    t = seasons.today(now)
    nxt = herdr.next_event(t)
    y = 32
    if day["events"]:
        y = draw_label("TERMINE", y)
        for e in day["events"]:
            if y + ROW > BOTTOM:
                return
            if e is nxt:
                draw_panel(6, y - 2, WIDTH - 12, ROW + 2)
            past = not e.get("x") and nxt is not None and e is not nxt and e["t"] < nxt["t"]
            display.set_pen(DIM_PEN if e.get("x") or past else TEXT_PEN)
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
                display.set_pen(DIM_PEN)
                display.text("+%d" % (len(day["tasks"]) - i), WIDTH - 30, y - ROW, -1, 1)
                return
            done = task.get("x")
            draw_checkbox(14, y, done)
            display.set_pen(DIM_PEN if done else TEXT_PEN)
            display.text(shorten(task["n"], (WIDTH - 34) // 6), 26, y, -1, 1)
            y += ROW


def draw_label(text, y):
    display.set_pen(DIM_PEN)
    display.text(text, 10, y, -1, 1)
    w = display.measure_text(text, 1)
    display.rectangle(14 + w, y + 3, WIDTH - 24 - w, 1)
    return y + 12


def draw_checkbox(x, y, done):
    if done:
        display.set_pen(TICK_PEN)
        display.rectangle(x, y, 7, 7)
    else:
        display.set_pen(DIM_PEN)
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
    display.set_pen(DIM_PEN)
    display.text(n, WIDTH - 12 - display.measure_text(n, 2), 10, -1, 2)
    blink = (now // 400) % 2 == 0
    for i, a in enumerate(agents[:MAX_AGENTS]):
        y = 34 + i * 38
        status = a.get("s", "unknown")
        colour = STATUS_PEN.get(status, DIM_PEN)
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
        display.set_pen(colour if status != "blocked" or blink else DIM_PEN)
        display.text(word, WIDTH - 14 - ww, y + 10, -1, 1)
        line = a.get("k", "")
        if a.get("t"):
            line = line + " - " + a["t"] if line else a["t"]
        display.set_pen(DIM_PEN)
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
        display.set_pen(DIM_PEN)
        label = shorten(spaces[0], 7)
        display.text(label, WIDTH - 12 - display.measure_text(label, 1), 14, -1, 1)
    blink = (now // 400) % 2 == 0
    y, last_space = 32, None
    for it in rows:
        if len(spaces) > 1 and it.get("w", "") != last_space:
            if y + 46 > HEIGHT - 10:
                break
            last_space = it.get("w", "")
            label = last_space.upper()
            lw = display.measure_text(label, 1)
            display.set_pen(DIM_PEN)
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
        display.set_pen(DIM_PEN)
        display.text(info, WIDTH - 14 - iw, y + 14, -1, 1)
        # left: MR / branch big, the title (or the failed job) below
        display.set_pen(TEXT_PEN)
        display.text(shorten(it.get("n", ""), (WIDTH - 62 - max(ww, iw)) // 12), 38, y + 5, -1, 2)
        if it.get("f"):
            display.set_pen(FAIL_PEN)
            line = "failed: " + it["f"]
        else:
            display.set_pen(DIM_PEN)
            line = it.get("t", "")
        display.text(shorten(line, (WIDTH - 52) // 6), 38, y + 22, -1, 1)
        y += 34


# --- home ----------------------------------------------------------------------

def home_key(now):
    return home.version(), tick_if(home.low_batteries(), now, 500)


def draw_home(now):
    person = home.person_state()
    at_home = person and person["state"] == "home"
    draw_header(HOUSE, 10, 9, TICK_PEN if at_home else IDLE_PEN, "HOME")
    if not home.HA_TOKEN or not home.ready():
        draw_waiting("Waiting for Home Assistant...")
        return
    if person:
        word = "DA" if at_home else "UNTERWEGS"
        display.set_pen(TICK_PEN if at_home else DIM_PEN)
        display.text(word, WIDTH - 12 - display.measure_text(word, 1), 14, -1, 1)
    draw_weather_tile()
    draw_rooms()
    # low batteries, one at a time
    low = home.low_batteries()
    if low:
        text = "BATTERIE " + low[(now // 3000) % len(low)]
        display.set_pen(FAIL_PEN if (now // 500) % 2 else DIM_PEN)
        display.text(text[:38], 10, 218, -1, 1)


def draw_weather_tile():
    cond, night = home.weather()
    w = home.weather_state()
    draw_panel(6, 32, WIDTH - 12, 58)
    draw_weather_icon(cond, night, 18, 41, 4)
    if not w:
        return
    a = w["attributes"]
    if a.get("temperature") is not None:
        draw_degrees("%d" % round(a["temperature"]), 82, 42, 4, TEXT_PEN)
    display.set_pen(TEXT_PEN)
    desc = home.CONDITION_DE.get(cond, (cond or "").upper())
    display.text(desc, WIDTH - 14 - display.measure_text(desc, 1), 44, -1, 1)
    info = []
    if a.get("humidity") is not None:
        info.append("%d%%" % round(a["humidity"]))
    if a.get("wind_speed") is not None:
        info.append("%d km/h" % round(a["wind_speed"]))
    info = "  ".join(info)
    display.set_pen(DIM_PEN)
    display.text(info, WIDTH - 14 - display.measure_text(info, 1), 58, -1, 1)


def draw_rooms():
    """Per room: light bulb, name, temperature and a flame while heating."""
    y = 96
    for label, temp_id, light_id in home.HAC.ROOMS:
        light = home.state(light_id)
        on = light and light["state"] == "on"
        draw_art(BULB, 12, y + 2, 3, ALERT_PEN if on else BULB_OFF_PEN)
        display.set_pen(TEXT_PEN if on else DIM_PEN)
        display.text(label, 34, y + 2, -1, 2)
        st = home.state(temp_id)
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
    draw_header(GEAR, 12, 9, DIM_PEN, "SETTINGS")
    for i, (key, label, hint) in enumerate(SETTING_ROWS):
        y = SETTING_Y0 + i * SETTING_H
        on = prefs.settings[key]
        draw_panel(6, y, WIDTH - 12, SETTING_H - 4)
        display.set_pen(TEXT_PEN if on else DIM_PEN)
        display.text(label, 16, y + 5, -1, 2)
        display.set_pen(DIM_PEN)
        display.text(hint, 16, y + 23, -1, 1)
        # pixel toggle switch: knob right and green when on
        sx, sy = WIDTH - 62, y + 7
        display.set_pen(PANEL_LO_PEN)
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


# --- showing a page --------------------------------------------------------------

PAGES = {  # view -> (key, draw)
    "today": (today_key, draw_today),
    "agents": (agents_key, draw_agents),
    "pipelines": (pipelines_key, draw_pipelines),
    "home": (home_key, draw_home),
    "settings": (settings_key, draw_settings),
}
_shown = None  # (view, key) on screen right now


def show(view, now):
    """Draw the page if it changed; returns whether it did."""
    global _shown
    key_of, draw = PAGES[view]
    key = (view, key_of(now))
    if key == _shown:
        return False
    draw(now)
    draw_page_dots(view)
    _shown = key
    return True


def forget():
    """The scene drew over the screen: draw the next page in full again."""
    global _shown
    _shown = None
