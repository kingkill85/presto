# The meadow follows the seasons, and so do the things flying around:
#   spring  fresh green, tulips and daisies, petals blowing past
#   summer  tall grass, poppies, dandelions, a butterfly; fireflies at night
#   autumn  leaf piles, fly agarics, acorns, leaves falling
#   winter  frosty grass, snow left over, a frozen puddle, glints of frost
# and the holidays: eggs at Easter, a pumpkin at Halloween, a little tree
# from the first Advent to Epiphany, fireworks on New Year's Eve.
# When it snows the meadow is covered in snow whatever the season.

import math
import random
import time
import tz

from messy import home, particles
from messy.gfx import HEIGHT, WIDTH, blit, display, pen, runs_from_grid
from messy.sprites import GROUND

# --- the date ------------------------------------------------------------------

_today = None  # tz.localtime() once the clock is set, refreshed every 20 s
_checked = -100000


def today(now):
    global _today, _checked
    if time.ticks_diff(now, _checked) > 20000:
        _checked = now
        _today = tz.localtime() if time.gmtime()[0] >= 2024 else None  # RTC starts in 2021
    return _today


def season(t):
    m = t[1] if t else 6
    return ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer",
            "autumn", "autumn", "autumn", "winter")[m - 1]


def _day(y, m, d):
    return time.mktime((y, m, d, 0, 0, 0, 0, 0)) // 86400


def easter(y):
    """(month, day) of Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, kk = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - kk) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    n = h + l - 7 * m + 114
    return n // 31, n % 31 + 1


def holiday(t):
    """"eggs", "pumpkin", "tree" or None for the date t."""
    if not t:
        return None
    y, mo, d = t[0], t[1], t[2]
    today_n = _day(y, mo, d)
    em, ed = easter(y)
    if -7 <= today_n - _day(y, em, ed) <= 1:  # Palm Sunday to Easter Monday
        return "eggs"
    if mo == 10 and d >= 20:
        return "pumpkin"
    if mo == 1 and d <= 6:
        return "tree"
    if mo in (11, 12):  # from the first Advent: the Sunday from Nov 27 on
        nov27 = _day(y, 11, 27)
        weekday = time.localtime(nov27 * 86400)[6]  # Monday is 0
        if today_n >= nov27 + (6 - weekday) % 7:
            return "tree"
    return None


def fireworks(t):
    return bool(t) and ((t[1] == 12 and t[2] == 31 and t[3] >= 18) or (t[1] == 1 and t[2] == 1 and t[3] < 2))


NIGHT_FROM, NIGHT_TO = 22, 6  # hours Messy and Clawd sleep (unless there's work)


def bedtime(now):
    """Between 22:00 and 6:00 (once the clock is set)."""
    t = today(now)
    return bool(t) and (t[3] >= NIGHT_FROM or t[3] < NIGHT_TO)


def is_night(t):
    if home.weather_state():
        return home.weather()[1]
    return bool(t) and (t[3] >= 21 or t[3] < 6)


# --- the meadow ------------------------------------------------------------------
# 4 px blocks: DECO rows for flowers and things above the ground, a row of
# tufts, grass, then soil with pebbles down to the bottom of the screen.

FLOOR_PENS = {
    "L": pen((140, 230, 80)), "M": pen((60, 196, 72)), "D": pen((24, 132, 60)),      # spring grass
    "T": pen((0, 228, 54)), "G": pen((0, 168, 81)), "g": pen((0, 112, 62)),         # summer grass
    "A": pen((120, 160, 60)), "B": pen((86, 128, 54)), "b": pen((62, 96, 46)),       # autumn grass
    "X": pen((128, 140, 104)), "Y": pen((98, 112, 86)), "y": pen((74, 88, 70)),      # winter grass
    "F": pen((206, 220, 232)),                                                       # frost
    "k": pen((255, 119, 168)), "v": pen((255, 236, 39)), "f": pen((255, 241, 232)),  # flowers
    "q": pen((255, 0, 77)), "z": pen((180, 110, 230)), "h": pen((40, 20, 30)),       # poppy, purple, centre
    "o": pen((255, 163, 0)), "r": pen((200, 60, 40)), "n": pen((171, 82, 54)),       # leaves
    "c": pen((225, 30, 40)), "a": pen((190, 125, 55)),                               # fly agaric, acorn
    "s": pen((122, 74, 50)), "S": pen((92, 54, 40)),                                 # soil
    "p": pen((95, 87, 79)), "P": pen((158, 148, 136)),                               # pebbles
    "W": pen((240, 242, 250)), "w": pen((184, 194, 220)), "u": pen((140, 152, 190)),  # snow, shade
    "e": pen((92, 66, 60)), "E": pen((70, 50, 50)),                                  # frozen soil
    "I": pen((150, 200, 240)), "i": pen((230, 245, 255)),                            # ice
}
DECO = 4  # rows above the tufts
FLOOR_ROWS = (HEIGHT - GROUND) // 4 + 2
TOP = DECO  # the row of tufts, just above the ground line
FLOOR_Y = GROUND - 4 - DECO * 4  # where the grid is drawn
SEASON_GRASS = {"spring": "LMD", "summer": "TGg", "autumn": "ABb", "winter": "XYy"}
SHADOWS = {  # a darker shade of what's on the ground
    "spring": pen((20, 110, 45)), "summer": pen((0, 84, 48)), "autumn": pen((50, 74, 32)),
    "winter": pen((150, 162, 196)),
}

# small things standing on the grass ("x" and "y" take a colour)
TULIP = ("x.x", "xxx", ".D.", ".D.")
DAISY = (".f.", "fvf", ".f.", ".D.")
TALL_GRASS = ("T..T", "T.TG", "GTGG")
POPPY = (".q.", "qhq", ".q.", ".g.", ".g.")
DANDELION = (".f.", "f.f", ".f.", ".g.", ".g.")
LEAF_PILE = ("..o..", ".rno.", "onrno")
FLY_AGARIC = (".cfc.", "cfccc", "..f..", "..f..")
ACORN = ("S", "a")
EGG = (".x.", "xyx", "xxx")
EGG_COLOURS = (("k", "f"), ("v", "q"), ("I", "f"), ("z", "v"), ("M", "v"))

_floors = {}


def _stamp(g, art, c, bottom, x="", y=""):
    """Put art into the grid with its last row on row `bottom`."""
    top = bottom - len(art) + 1
    for i, row in enumerate(art):
        r = top + i
        for j, ch in enumerate(row):
            if ch != "." and 0 <= r < len(g) and 0 <= c + j < len(g[0]):
                g[r][c + j] = x if ch == "x" else y if ch == "y" else ch


def floor_runs(snow, sea, deco):
    key = (snow, sea, deco)
    runs = _floors.get(key)
    if runs is not None:
        return runs
    cols = WIDTH // 4
    seed = [12345]

    def rnd(n):  # same meadow every time
        seed[0] = (seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return seed[0] % n

    g = [["."] * cols for _ in range(DECO + FLOOR_ROWS)]
    ground = TOP + 1  # first row below the ground line
    if snow or sea == "winter":
        _winter(g, cols, rnd, deep=snow)
    else:
        light, mid, dark = SEASON_GRASS[sea]
        for c in range(cols):
            if rnd(3 if sea == "summer" else 5) == 0:
                g[TOP][c] = light
            g[TOP + 1][c] = light if rnd(4) == 0 else mid
            g[TOP + 2][c] = dark if rnd(3) == 0 else mid
            g[TOP + 3][c] = "S" if rnd(3) else dark
            for r in range(TOP + 4, len(g)):
                g[r][c] = "S" if rnd(6) == 0 else "s"
    if not snow and sea != "winter":
        if sea == "spring":
            for _ in range(cols // 4):  # little flowers in the tufts
                c = rnd(cols)
                g[TOP][c] = "kvf"[rnd(3)]
                g[TOP + 1][c] = dark
            for _ in range(7):
                _stamp(g, TULIP, rnd(cols - 3), ground, "qkvz"[rnd(4)])
            for _ in range(6):
                _stamp(g, DAISY, rnd(cols - 3), ground)
        elif sea == "summer":
            for _ in range(cols // 6):
                _stamp(g, TALL_GRASS, rnd(cols - 4), ground)
            for _ in range(5):
                _stamp(g, POPPY, rnd(cols - 3), ground)
            for _ in range(3):
                _stamp(g, DANDELION, rnd(cols - 3), ground)
        elif sea == "autumn":
            for _ in range(cols // 3):  # fallen leaves
                g[TOP + 1 + rnd(2)][rnd(cols)] = "orn"[rnd(3)]
            for _ in range(4):
                _stamp(g, LEAF_PILE, rnd(cols - 5), ground)
            for _ in range(2):
                _stamp(g, FLY_AGARIC, rnd(cols - 5), ground)
            for _ in range(6):
                _stamp(g, ACORN, rnd(cols), ground)
    if deco == "eggs":
        for _ in range(6):
            x, y = EGG_COLOURS[rnd(len(EGG_COLOURS))]
            _stamp(g, EGG, rnd(cols - 3), ground, x, y)
    for _ in range(cols // 4):  # pebbles
        c, r = rnd(cols - 2), TOP + 4 + rnd(FLOOR_ROWS - 5)
        g[r][c] = g[r][c + 1] = "p"
        g[r][c] = "P"
    runs = runs_from_grid(g, FLOOR_PENS, 0)
    _floors[key] = runs
    return runs


def _winter(g, cols, rnd, deep):
    """A blanket of snow with blue shade, little drifts and frozen soil below.
    Without fresh snow, dry stalks poke through and a puddle is frozen."""
    for c in range(cols):
        g[TOP + 1][c] = "W"
        g[TOP + 2][c] = "w" if rnd(3) else ("W" if deep else "u")
        g[TOP + 3][c] = "u" if rnd(3) == 0 else "E"
        for r in range(TOP + 4, len(g)):
            g[r][c] = "E" if rnd(5) == 0 else "e"
    for _ in range(5 if deep else 3):  # drifts: humps with a shaded right side
        c0, n = rnd(cols - 8), 4 + rnd(5)
        for c in range(c0, c0 + n):
            g[TOP][c] = "W"
        g[TOP][c0 + n - 1] = "w"
        if n >= 6:
            for c in range(c0 + 2, c0 + n - 2):
                g[TOP - 1][c] = "W"
            g[TOP - 1][c0 + n - 3] = "w"
    if deep:
        return
    for _ in range(cols // 5):  # dry stalks poking through
        c = rnd(cols)
        if g[TOP][c] == ".":
            g[TOP][c] = "y"
            if rnd(2):
                g[TOP - 1][c] = "Y"
    for c in range(43, 54):  # a frozen puddle
        g[TOP + 1][c] = "i" if c in (45, 46, 50) else "I"
        if 44 <= c <= 52:
            g[TOP + 2][c] = "I" if 45 <= c <= 51 else "u"
        g[TOP][c] = "." if g[TOP][c] in ("W", "w", "y") else g[TOP][c]


def draw_meadow(now, snow):
    """Draw the meadow and the holiday things; returns the shadow colour."""
    t = today(now)
    sea, deco = season(t), holiday(t)
    blit(floor_runs(snow, sea, "eggs" if deco == "eggs" else None), 0, FLOOR_Y, 4)
    if deco == "pumpkin":
        draw_pumpkin(now, is_night(t))
    elif deco == "tree":
        draw_tree(now)
    return SHADOWS["winter" if snow else sea]


# --- holiday things --------------------------------------------------------------

DECO_X = 98  # between Messy and Clawd
PUMPKIN = ("...G...", ".ooOoo.", "oyoOoyo", "ooOOOoo", "oyyyyyo", ".ooOoo.")
PUMPKIN_PENS = {"o": pen((255, 140, 0)), "O": pen((205, 95, 0)), "G": pen((0, 112, 62)),
                "y": pen((255, 236, 39)), "Y": pen((150, 60, 0))}
TREE = ("...v...", "...g...", "..ggg..", ".ggggg.", "..ggg..", ".ggggg.", "ggggggg", "...b...")
TREE_PENS = {"v": pen((255, 236, 39)), "g": pen((0, 120, 60)), "b": pen((120, 70, 40))}
TREE_LIGHTS = ((3, 2), (1, 3), (4, 3), (2, 5), (5, 5), (1, 6), (3, 6), (6, 6))
LIGHT_PENS = (pen((255, 0, 77)), pen((255, 236, 39)), pen((41, 173, 255)), pen((255, 119, 168)))
_holiday_runs = {}


def _runs(name, art, pens):
    runs = _holiday_runs.get(name)
    if runs is None:
        runs = _holiday_runs[name] = runs_from_grid(art, pens, 0)
    return runs


def draw_pumpkin(now, night):
    """A carved pumpkin; at night the candle inside flickers."""
    dark = night and (now // 120) % 7 == 0
    art = PUMPKIN if not dark else tuple(row.replace("y", "Y") for row in PUMPKIN)
    blit(_runs("pumpkin_dark" if dark else "pumpkin", art, PUMPKIN_PENS), DECO_X, GROUND - 6 * 4 + 4, 4)


def draw_tree(now):
    """A little Christmas tree with blinking lights."""
    y = GROUND - 8 * 4 + 4
    blit(_runs("tree", TREE, TREE_PENS), DECO_X, y, 4)
    step = now // 500
    for i, (c, r) in enumerate(TREE_LIGHTS):
        p = LIGHT_PENS[(i + step) % len(LIGHT_PENS)]
        display.set_pen(p)
        display.rectangle(DECO_X + c * 4 + 1, y + r * 4 + 1, 2, 2)


# --- things flying around --------------------------------------------------------

PETAL_PENS = (pen((255, 183, 206)), pen((255, 241, 232)))
LEAF_PENS = (pen((255, 163, 0)), pen((200, 60, 40)), pen((171, 82, 54)))
BUTTERFLY_PENS = (pen((255, 236, 39)), pen((41, 173, 255)), pen((255, 119, 168)))
FIREFLY_PEN = pen((200, 255, 80))
FIREWORK_PENS = (pen((255, 0, 77)), pen((255, 236, 39)), pen((41, 173, 255)), pen((0, 228, 54)),
                 pen((255, 119, 168)))


def spawn(now, k):
    """Start new seasonal particles now and then (call every frame on the scene)."""
    t = today(now)
    if fireworks(t) and random.random() < 0.03 * k:
        _firework()
    if home.weather()[0] in home.RAIN + home.SNOW:
        return  # nothing flies in the rain or snow
    sea, night = season(t), is_night(t)
    if sea == "spring" and not night:
        if particles.count("petal") < 6 and random.random() < 0.03 * k:
            particles.spawn("petal", WIDTH + 4, random.randint(40, GROUND - 20), -random.uniform(0.8, 1.4), 0, 280,
                            random.choice(PETAL_PENS))
    elif sea == "summer":
        if night:
            if particles.count("firefly") < 6 and random.random() < 0.05 * k:
                particles.spawn("firefly", random.randint(10, WIDTH - 10), GROUND - random.randint(10, 70), 0, 0,
                                random.randint(100, 180), FIREFLY_PEN)
        elif not particles.count("butterfly") and random.random() < 0.004 * k:
            particles.spawn("butterfly", -6, random.randint(120, GROUND - 30), random.uniform(0.7, 1.1), 0, 400,
                            random.choice(BUTTERFLY_PENS))
    elif sea == "autumn":
        if particles.count("leaf") < 5 and random.random() < 0.025 * k:
            particles.spawn("leaf", random.randint(0, WIDTH), -6, 0, random.uniform(0.5, 0.8), 400,
                            random.choice(LEAF_PENS))
    elif sea == "winter" and random.random() < 0.04 * k:
        particles.spawn("glint", random.randint(4, WIDTH - 4), GROUND + random.randint(-2, 6), 0, 0, 8)


def _firework():
    x, y = random.randint(30, WIDTH - 30), random.randint(30, 110)
    colour = random.choice(FIREWORK_PENS)
    for i in range(12):
        a = i * math.pi / 6
        particles.spawn("pop", x, y, 2.2 * math.cos(a), 2.2 * math.sin(a), random.randint(10, 15), colour)
