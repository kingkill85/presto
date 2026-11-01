# The main page: sky and weather, the big clock, the meadow, the hamster wheel,
# both characters and the little particles flying around.

import math
import network
import ntptime
import time
import tz

from messy import herdr, home
from messy.gfx import (ALERT_PEN, ANGER, BACKGROUND, CLAWD_PEN, CLOCK, CROSS, CRUMB_PEN, DOT_PEN, EXCL, FAIL_PEN,
                       FUR_PEN, GEAR_A, GEAR_B, HEART, HEART_PEN, HEIGHT, IDLE_PEN, MANUAL_PEN, NOTE, PLAY,
                       RING_SMALL, SEED_ART, SEED_PEN, SHADOW, SLASH, SNOW_SHADOW, SPARK, SPARK_PEN, SPARK_X,
                       STAND_PEN, TICK, TICK_PEN, WHEEL_DARK_PEN, WHEEL_PEN, WIDTH, WOOL_PEN, ZED, ZED_PEN, blit,
                       display, draw_alert_sign, draw_art, draw_bubble, draw_degrees, pen, runs_from_grid)
from messy.sprites import (BASE_Y, C_BASE_Y, CS, GROUND, HOME_X, S, draw_clawd, draw_hamster, draw_leaf_umbrella,
                           draw_umbrella)

_wlan = network.WLAN(network.STA_IF)

# --- sky -------------------------------------------------------------------------
# Background, clock and date colours follow the sun's elevation (degrees):
# night, twilight, dusk, day. Checked every few seconds.

SKY_STOPS = ((-12, (10, 14, 34)), (-6, (16, 22, 52)), (0, (42, 42, 92)), (6, (55, 72, 132)),
             (15, (62, 100, 168)), (90, (72, 118, 190)))
FLASH_PEN = pen((150, 160, 200))
DARK_CLOUD_PEN = pen((55, 60, 90))
RAIN_PEN = pen((90, 140, 220))
SNOW_PEN = pen((230, 235, 245))
FOG_PEN = pen((128, 138, 168))
FOG_BACK_PEN = pen((92, 102, 136))
SUN_PEN = pen((255, 210, 60))
MOON_PEN = pen((230, 230, 200))
STAR_PEN = pen((200, 200, 230))
CLOCK_PEN = pen((55, 75, 135))  # changed with the sky
DATE_PEN = pen((95, 110, 165))
sky_pen = None  # None until the sun's elevation is known
_sky_checked = -100000

SUN_ART = ("#..#..#", ".#####.", ".#####.", "#######", ".#####.", ".#####.", "#..#..#")
MOON_ART = ("..###.", ".##...", "##....", "##....", ".##...", "..###.")
CLOUD_ART = ("...###.....", "..#####.##.", ".##########", "###########", ".#########.")
BOLT_ART = ("..#", ".#.", "###", ".#.", "#..")
STARS = [((i * 67 + 11) % WIDTH, 6 + (i * 37) % 100) for i in range(16)]


def sky_rgb(elevation):
    for (e0, c0), (e1, c1) in zip(SKY_STOPS, SKY_STOPS[1:]):
        if elevation <= e1:
            u = max(0.0, min(1.0, (elevation - e0) / (e1 - e0)))
            return tuple(int(a + (b - a) * u) for a, b in zip(c0, c1))
    return SKY_STOPS[-1][1]


def _update_sky_colours(now):
    global sky_pen, _sky_checked, CLOCK_PEN, DATE_PEN
    if time.ticks_diff(now, _sky_checked) < 5000:
        return
    _sky_checked = now
    sun = home.sun_state()
    if not sun or sun["attributes"].get("elevation") is None:
        return
    r, g, b = sky_rgb(sun["attributes"]["elevation"])
    sky_pen = pen((r, g, b))
    CLOCK_PEN = pen((min(255, r + 42), min(255, g + 52), min(255, b + 70)))
    DATE_PEN = pen((min(255, r + 80), min(255, g + 84), min(255, b + 90)))


def sky_background(now):
    cond, _ = home.weather()
    if cond in home.THUNDER and now % 9000 < 110:
        return FLASH_PEN
    _update_sky_colours(now)
    return sky_pen or BACKGROUND


def draw_sky(now):
    """Weather: symbol top left, stars at night, rain, snow (fog: draw_fog)."""
    cond, night = home.weather()
    if not cond:
        return
    if night:
        display.set_pen(STAR_PEN)
        for i, (sx, sy) in enumerate(STARS):
            # each star dims briefly about every 9 s, all at different times
            if (now + i * 1370) % 9000 >= 200:
                display.rectangle(sx, sy, 2, 2)
    draw_weather_icon(cond, night, 9, 3, 3)
    if cond in home.RAIN:
        display.set_pen(RAIN_PEN)
        n = 40 if cond == "pouring" else 24
        for i in range(n):
            ry = int(i * 53 + now * 0.22) % GROUND
            display.rectangle((i * 37 + ry // 8) % WIDTH, ry, 2, 6)
    if cond in home.SNOW:
        display.set_pen(SNOW_PEN)
        for i in range(30):
            fy = int(i * 29 + now * 0.035) % GROUND
            display.rectangle(int(i * 41 + 6 * math.sin(now / 700 + i)) % WIDTH, fy, 3, 3)


def draw_weather_icon(cond, night, x, y, s):
    """Sun or moon, behind clouds if there are any, with rain, snow or a bolt."""
    if night:
        draw_art(MOON_ART, x + s, y, s, MOON_PEN)
    else:
        draw_art(SUN_ART, x, y, s, SUN_PEN)
    if cond not in ("sunny", "clear-night", None):
        dark = cond in ("rainy", "pouring", "lightning", "lightning-rainy", "hail", "snowy-rainy")
        draw_art(CLOUD_ART, x - s, y + 3 * s, s, DARK_CLOUD_PEN if dark else WHEEL_PEN)
    if cond in home.RAIN:
        display.set_pen(RAIN_PEN)
        for i in range(4):
            display.rectangle(x + i * 3 * s, y + 9 * s, s, 2 * s)
    if cond in home.SNOW:
        display.set_pen(SNOW_PEN)
        for i in range(4):
            display.rectangle(x + i * 3 * s + s, y + 9 * s + (i % 2) * s, s, s)
    if cond in home.THUNDER:
        draw_art(BOLT_ART, x + 4 * s, y + 7 * s, s, ALERT_PEN)


def draw_weather_line():
    """Temperature and condition below the clock."""
    if not home.weather_state():
        return
    cond, _ = home.weather()
    t = home.temperature()
    temp = "%d" % round(t) if t is not None else ""
    desc = home.CONDITION_DE.get(cond, (cond or "").upper())
    tw = display.measure_text(temp, 2) + 12 if temp else 0
    x, y = (WIDTH - tw - display.measure_text(desc, 1)) // 2, 94
    if temp:
        draw_degrees(temp, x, y, 2, DATE_PEN)
    display.set_pen(DATE_PEN)
    display.text(desc, x + tw, y + 4, -1, 1)


# --- clock -----------------------------------------------------------------------
# 3x5 pixel digits drawn with 10 px blocks, weekday and date above.

DIGITS = {
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"), "3": ("###", "..#", ".##", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"), "7": ("###", "..#", ".#.", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "###"),
}
WEEKDAYS = ("MONTAG", "DIENSTAG", "MITTWOCH", "DONNERSTAG", "FREITAG", "SAMSTAG", "SONNTAG")
CLOCK_BLOCK = 10
clock_synced = False
_next_sync = 0


def sync_clock(now):
    """Set the RTC from NTP once WiFi is up; retry every 10 s until it works."""
    global clock_synced, _next_sync
    if clock_synced or time.ticks_diff(now, _next_sync) < 0 or not _wlan.isconnected():
        return
    _next_sync = time.ticks_add(now, 10000)
    try:
        ntptime.settime()
        clock_synced = True
    except Exception:
        pass


def draw_clock(now):
    if not clock_synced:
        return
    t = tz.localtime()
    b = CLOCK_BLOCK
    text = "%02d:%02d" % (t[3], t[4])
    width = 17 * b  # four digits of 3 blocks with 1 block gaps, plus the colon
    x, y = (WIDTH - width) // 2, 34
    for ch in text:
        if ch == ":":
            if (now // 1000) % 2 == 0:
                display.set_pen(CLOCK_PEN)
                display.rectangle(x, y + b, b, b)
                display.rectangle(x, y + 3 * b, b, b)
            x += 2 * b
            continue
        draw_art(DIGITS[ch], x, y, b, CLOCK_PEN)
        x += 4 * b
    # centred, but clear of the weather symbol in the corner; long weekdays
    # are shortened when they don't fit
    left = 46 if home.weather_state() else 8
    date = "%s %d.%d." % (WEEKDAYS[t[6]], t[2], t[1])
    if display.measure_text(date, 2) > WIDTH - left - 6:
        date = "%s %d.%d." % (WEEKDAYS[t[6]][:2], t[2], t[1])
    dw = display.measure_text(date, 2)
    display.set_pen(DATE_PEN)
    display.text(date, max(left, (WIDTH - dw) // 2), 12, -1, 2)


# --- meadow ------------------------------------------------------------------------
# A strip of pixel meadow (4 px blocks) that follows the seasons: spring
# flowers, lush summer grass, autumn leaves, frosty winter grass, and covered
# in snow when it snows. Grass on top, soil with pebbles below.

FLOOR_PENS = {
    "T": pen((0, 228, 54)), "G": pen((0, 168, 81)), "g": pen((0, 112, 62)),         # spring/summer grass
    "A": pen((120, 160, 60)), "B": pen((86, 128, 54)), "b": pen((62, 96, 46)),       # autumn grass
    "X": pen((128, 140, 104)), "Y": pen((98, 112, 86)), "y": pen((74, 88, 70)),      # winter grass
    "F": pen((206, 220, 232)),                                                       # frost
    "k": pen((255, 119, 168)), "v": pen((255, 236, 39)), "f": pen((255, 241, 232)),  # flowers
    "o": pen((255, 163, 0)), "r": pen((200, 60, 40)), "n": pen((171, 82, 54)),       # leaves
    "s": pen((122, 74, 50)), "S": pen((92, 54, 40)),                                 # soil
    "p": pen((95, 87, 79)), "P": pen((158, 148, 136)),                               # pebbles
    "W": pen((240, 242, 250)), "w": pen((184, 194, 220)),                            # snow
}
FLOOR_ROWS = (HEIGHT - GROUND) // 4 + 2  # one row of tufts above the ground line
SEASON_GRASS = {"spring": "TGg", "summer": "TGg", "autumn": "ABb", "winter": "XYy"}
_floors = {}


def season():
    m = tz.localtime()[1] if clock_synced else 6
    return ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer",
            "autumn", "autumn", "autumn", "winter")[m - 1]


def floor_runs(snow, sea):
    key = (snow, sea)
    runs = _floors.get(key)
    if runs is not None:
        return runs
    cols = WIDTH // 4
    seed = [12345]

    def rnd(n):  # same meadow every time
        seed[0] = (seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return seed[0] % n

    light, mid, dark = SEASON_GRASS[sea]
    g = [["."] * cols for _ in range(FLOOR_ROWS)]
    for c in range(cols):
        if snow:
            if rnd(5) == 0:
                g[0][c] = "W"
            g[1][c] = "W" if rnd(4) else "w"
            g[2][c] = "w" if rnd(3) == 0 else "W"
        else:
            if rnd(3 if sea == "summer" else 5) == 0:
                g[0][c] = "F" if sea == "winter" and rnd(2) else light
            g[1][c] = light if rnd(4) == 0 else mid
            g[2][c] = dark if rnd(3) == 0 else mid
        g[3][c] = "S" if rnd(3) else dark
        for r in range(4, FLOOR_ROWS):
            g[r][c] = "S" if rnd(6) == 0 else "s"
    if not snow:
        if sea in ("spring", "summer"):  # flowers on little stems
            for _ in range(cols // (4 if sea == "spring" else 8)):
                c = rnd(cols)
                g[0][c] = "kvf"[rnd(3)] if sea == "spring" else "v"
                g[1][c] = dark
        elif sea == "autumn":  # fallen leaves
            for _ in range(cols // 3):
                c, r = rnd(cols), 1 + rnd(2)
                g[r][c] = "orn"[rnd(3)]
        else:  # frost on the grass
            for _ in range(cols // 4):
                g[1][rnd(cols)] = "F"
    for _ in range(cols // 4):  # pebbles
        c, r = rnd(cols - 2), 4 + rnd(FLOOR_ROWS - 5)
        g[r][c] = g[r][c + 1] = "p"
        g[r][c] = "P"
    runs = runs_from_grid(g, FLOOR_PENS, 0)
    _floors[key] = runs
    return runs


def draw_ground(sky, shadows):
    """Clear to the sky colour, draw the meadow and a shadow per (x, width)."""
    display.set_pen(sky)
    display.clear()
    snow = home.weather()[0] in home.SNOW
    blit(floor_runs(snow, season()), 0, GROUND - 4, 4)
    # shadows shrink while their owner is in the air
    display.set_pen(SNOW_SHADOW if snow else SHADOW)
    for cx, w in shadows:
        w = max(4, int(w))
        display.rectangle(int(cx) - w // 2, GROUND, w, 4)


FOG_PUFF = ("......######......", "...############...", ".################.", "##################")


def draw_fog(now):
    """Fog banks behind everyone: puffs drifting in two layers, the back one
    slower, so they slide past each other."""
    span = WIDTH + 80
    for i in range(4):  # back layer
        x = int(i * span / 4 + now * 0.004) % span - 72
        draw_art(FOG_PUFF, x // 4 * 4, GROUND - 34 - (i % 2) * 6, 4, FOG_BACK_PEN)
    for i in range(3):  # front layer
        x = int(i * span / 3 + 40 + now * 0.009) % span - 72
        draw_art(FOG_PUFF, x // 4 * 4, GROUND - 20 + (i % 2) * 4, 4, FOG_PEN)


# --- hamster wheel -------------------------------------------------------------------
# Rim blocks at fixed spots (pixel-stable); the rotation is shown by colours
# moving along the rim and by turning spokes. The rim fills up in blue as the
# jobs of the running pipelines finish.

WHEEL_R = 46
WHEEL_CX = HOME_X + 8 * S + 4  # the wheel stands where the hamster lives
WHEEL_CY = GROUND - WHEEL_R - 4
WHEEL_RIM = [(int(WHEEL_R * math.cos(i * math.pi / 15)), int(WHEEL_R * math.sin(i * math.pi / 15))) for i in range(30)]
WHEEL_LIFT = 8  # the hamster runs on the inside of the rim, a bit above the floor
RIM_TOP = len(WHEEL_RIM) * 3 // 4  # rim block at 12 o'clock
PROGRESS_PEN = MANUAL_PEN
PROGRESS_DARK_PEN = pen((20, 110, 190))


def draw_wheel_back(cx, turn):
    # A-frame stand
    display.set_pen(STAND_PEN)
    for i in range(0, WHEEL_R + 4, 4):
        display.rectangle(cx - i * 5 // 8 - 2, WHEEL_CY + i, 5, 5)
        display.rectangle(cx + i * 5 // 8 - 2, WHEEL_CY + i, 5, 5)
    # spokes
    display.set_pen(WHEEL_DARK_PEN)
    for k in range(4):
        a = turn + k * math.pi / 4
        ca, sa = math.cos(a), math.sin(a)
        for r in range(-WHEEL_R + 8, WHEEL_R - 6, 6):
            display.rectangle(cx + int(r * ca) - 2, WHEEL_CY + int(r * sa) - 2, 4, 4)
    display.set_pen(WHEEL_PEN)
    display.rectangle(cx - 4, WHEEL_CY - 4, 8, 8)


def draw_wheel_rim(cx, shift, broken):
    n = len(WHEEL_RIM)
    frac = None if broken else herdr.progress()
    filled = int(frac * n + 0.5) if frac is not None else 0
    for i, (dx, dy) in enumerate(WHEEL_RIM):
        if broken:
            display.set_pen(FAIL_PEN if i % 5 == 0 else WHEEL_DARK_PEN)
        elif (i - RIM_TOP) % n < filled:
            display.set_pen(PROGRESS_DARK_PEN if (i + shift) % 3 == 0 else PROGRESS_PEN)
        else:
            display.set_pen(WHEEL_DARK_PEN if (i + shift) % 3 == 0 else WHEEL_PEN)
        display.rectangle(cx + dx - 4, WHEEL_CY + dy - 4, 8, 8)


# --- agent icons -------------------------------------------------------------------

def draw_agent_bar(now):
    """One small icon per agent on the right edge of the scene."""
    x, y = WIDTH - 15, 36
    for a in herdr.agent_list[:5]:
        s = a.get("s")
        if s == "working":
            draw_art(SPARK if (now // 150) % 2 else SPARK_X, x, y, 3, CLAWD_PEN)
        elif s == "done":
            draw_art(TICK, x - 1, y, 2, TICK_PEN)
        elif s == "blocked":
            if (now // 400) % 2 == 0:
                draw_art(EXCL, x - 1, y - 1, 2, ALERT_PEN)
        else:
            draw_art(RING_SMALL, x, y, 3, IDLE_PEN)
        y += 14


def draw_pipe_bar(now):
    """One small icon per pipeline that ran since boot, with its last status,
    on the left edge of the scene below the weather symbol."""
    x, y = 6, 46
    for _, s in herdr.recent_pipes:
        if s == "running":
            draw_art(GEAR_A if (now // 200) % 2 else GEAR_B, x, y, 2, FUR_PEN)
        elif s == "failed":
            draw_art(CROSS, x, y, 2, FAIL_PEN)
        elif s == "success":
            draw_art(TICK, x, y, 2, TICK_PEN)
        elif s == "manual":
            draw_art(PLAY, x, y, 2, MANUAL_PEN)
        elif s in herdr.WAITING_STATES:
            draw_art(CLOCK, x, y, 2, WHEEL_PEN)
        else:  # canceled, skipped
            draw_art(SLASH, x, y, 2, IDLE_PEN)
        y += 14


# --- particles -------------------------------------------------------------------------
# [kind, x, y, vx, vy, life]; speeds and life are per 66 ms. They age on every
# page, otherwise they would pile up while another page is shown.

particles = []


def spawn(kind, x, y, vx, vy, life):
    particles.append([kind, x, y, vx, vy, life])


def update_particles(k):
    global particles
    for p in particles:
        p[1] += p[3] * k
        p[2] += p[4] * k
        p[5] -= k
        if p[0] == "crumb":  # falls and stays on the ground
            p[4] += 0.4 * k
            if p[2] >= GROUND - 3:
                p[2], p[3], p[4] = GROUND - 3, 0, 0
        elif p[0] == "zed":  # sways
            p[3] = 0.4 * math.sin(p[5] / 6)
    particles = [p for p in particles if p[5] > 0]


def draw_particles():
    for kind, x, y, _, _, life in particles:
        if kind == "crumb":
            display.set_pen(CRUMB_PEN)
            display.rectangle(int(x), int(y), 3, 3)
        elif kind == "heart":
            draw_art(HEART, x, y, 3, HEART_PEN)
        elif kind == "breath":
            size = 3 if life > 12 else 4 if life > 6 else 5
            display.set_pen(WOOL_PEN if life > 8 else ZED_PEN)
            display.rectangle(int(x), int(y), size, size)
        elif kind == "anger":
            draw_art(ANGER, x, y, 3, FAIL_PEN)
        elif kind == "note":
            draw_art(NOTE, x, y, 3, (ALERT_PEN, TICK_PEN, MANUAL_PEN, HEART_PEN)[int(x) % 4])
        elif kind == "smoke":
            display.set_pen(WHEEL_DARK_PEN if life > 12 else STAND_PEN)
            size = 6 if life > 15 else 4
            display.rectangle(int(x), int(y), size, size)
        elif kind == "spark":
            draw_art(SPARK, x, y, 3, SPARK_PEN)
        elif kind == "zed":
            draw_art(ZED, x, y, 3 if life > 25 else 2, ZED_PEN)


# --- the whole scene -------------------------------------------------------------------

def draw(now, messy, hp, clawd, cp, director, wear):
    """One frame of the scene. hp and cp are the poses (actors.Pose) of Messy
    and Clawd; the director (ball game, scene for two, pirate) draws its own
    extras."""
    x, c_x = messy.x, clawd.x
    jump, c_jump = hp.jump, cp.jump
    draw_ground(sky_background(now), ((x + 8 * S, 12 * S - jump), (c_x + 8 * CS, 14 * CS - c_jump)))
    draw_sky(now)
    draw_clock(now)
    draw_weather_line()
    draw_agent_bar(now)
    draw_pipe_bar(now)
    if home.weather()[0] == "fog":
        draw_fog(now)

    # Messy, in the wheel while a pipeline runs or after one failed
    state = messy.state
    in_wheel = state in ("wheel", "broken")
    if in_wheel:
        draw_wheel_back(WHEEL_CX, -messy.wheel_turn if state == "wheel" else 0.3)
        jump += WHEEL_LIFT
    y = BASE_Y - jump
    if not hp.hide:
        draw_hamster(x, y, hp, wear)
        if hp.umbrella:
            draw_leaf_umbrella(x, y + hp.bob * S)
    if in_wheel:
        draw_wheel_rim(WHEEL_CX, -int(messy.wheel_turn * 6) if state == "wheel" else 0, state == "broken")
        if state == "broken" and (now // 500) % 2 == 0:
            draw_art(CROSS, WHEEL_CX - 8, WHEEL_CY - WHEEL_R - 24, 3, FAIL_PEN)
    if hp.bubble == "tick":
        draw_art(TICK, x + 5 * S, y - 22, 4, TICK_PEN)
    elif hp.bubble == "name":
        draw_bubble("MESSY", int(x) + 2, y - 30)
    if hp.seed_y is not None:  # a seed falling from the sky
        draw_art(SEED_ART, x + 7 * S, hp.seed_y, S, SEED_PEN)

    # Clawd
    c_y = C_BASE_Y - c_jump
    if not cp.hide:
        draw_clawd(c_x, c_y, cp, wear)
        if cp.umbrella:
            draw_umbrella(c_x, c_y + cp.bob * CS)
    if cp.bubble == "!":
        draw_alert_sign(int(c_x) + 6 * CS, c_y - 30)
        display.set_pen(ALERT_PEN)
        display.rectangle(int(c_x) + 6 * CS + 4, c_y - 8, 4, 4)  # little tail
    elif cp.bubble == "tick":
        draw_art(TICK, int(c_x) + 5 * CS, c_y - 22, 4, TICK_PEN)
    elif cp.bubble == "name":
        draw_bubble("CLAWD", int(c_x) + 6, c_y - 30)
    if cp.laptop:  # Claude Code style spinner star
        draw_art(SPARK if (now // 150) % 2 else SPARK_X, int(c_x) + 14 * CS, C_BASE_Y - 12, 3, CLAWD_PEN)
    if cp.think:
        display.set_pen(DOT_PEN)
        for i in range(min(3, cp.think)):
            display.rectangle(int(c_x) + 11 * CS + i * 7, C_BASE_Y - 10, 4, 4)

    if director:
        director.draw(now)
    draw_particles()
