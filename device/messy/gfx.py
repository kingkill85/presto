# Screen, palette and the small drawing helpers everything else builds on.
#
# Building a sprite pixel by pixel is slow in MicroPython (a dict with a few
# hundred entries takes ~100 ms here), so every pose is built once into a grid,
# turned into horizontal runs of one colour and cached. Drawing a cached pose is
# just a handful of rectangles.

from presto import Presto

presto = Presto(ambient_light=False, full_res=False, layers=1)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()  # 240x240, every pixel doubled
touch = presto.touch
display.set_font("bitmap8")


def pen(rgb):
    return display.create_pen(*rgb)


# --- palette (PICO-8) ---------------------------------------------------------

BACKGROUND = pen((29, 43, 83))
COLOURS = {  # the hamster
    "#": pen((255, 163, 0)),    # fur
    "o": pen((255, 241, 232)),  # belly and face
    "p": pen((255, 119, 168)),  # ears, nose, paws, feet
    "e": pen((0, 0, 0)),        # eyes, mouth, seed, sunglasses
    "r": pen((255, 0, 77)),     # beanie
    "R": pen((126, 37, 83)),    # its stripes
}
FUR_PEN = COLOURS["#"]
SEED_PEN = COLOURS["e"]
HAT_PEN = COLOURS["r"]
WOOL_PEN = COLOURS["o"]
LEAF_PEN = pen((0, 168, 81))
LEAF_DARK_PEN = pen((0, 110, 60))
UMBRELLA_PEN = pen((255, 0, 77))
UMBRELLA_TIP_PEN = pen((255, 241, 232))
HANDLE_PEN = pen((60, 50, 50))
HEART_PEN = pen((255, 0, 77))
ZED_PEN = pen((194, 195, 199))
CRUMB_PEN = pen((255, 204, 170))
CLAWD_PEN = pen((217, 119, 87))
EYE_PEN = pen((0, 0, 0))
BALL_PEN = pen((255, 241, 232))
SPARK_PEN = pen((255, 236, 39))
DOT_PEN = pen((194, 195, 199))
LAPTOP_PEN = pen((95, 87, 79))
LAPTOP_EDGE_PEN = pen((194, 195, 199))
TICK_PEN = pen((0, 228, 54))
ALERT_PEN = pen((255, 236, 39))
TEXT_PEN = pen((255, 241, 232))
FAIL_PEN = pen((255, 0, 77))
MANUAL_PEN = pen((41, 173, 255))
WHEEL_PEN = pen((194, 195, 199))
WHEEL_DARK_PEN = pen((95, 87, 79))
STAND_PEN = pen((131, 118, 156))
DIM_PEN = pen((131, 118, 156))
IDLE_PEN = pen((95, 87, 79))
PANEL_PEN = pen((45, 60, 110))
PANEL_HI_PEN = pen((75, 95, 160))
PANEL_LO_PEN = pen((15, 22, 45))

# --- small pixel art, drawn in one colour with draw_art -----------------------

HEART = (".#.#.", "#####", "#####", ".###.", "..#..")
ZED = ("####", "..#.", ".#..", "####")
SPARK = (".#.", "###", ".#.")
SPARK_X = ("#.#", ".#.", "#.#")
TICK = ("....#", "...##", "#.##.", "###..", ".#...")
EXCL = ("..#..", ".###.", ".###.", "..#..", ".....", "..#..")
QMARK = (".###.", "#...#", "...#.", "..#..", ".....", "..#..")
RING = (".###.", "#...#", "#...#", "#...#", ".###.")
RING_SMALL = (".#.", "#.#", ".#.")
GEAR_A = ("#.#.#", ".###.", "##.##", ".###.", "#.#.#")
GEAR_B = ("..#..", "#####", "##.##", "#####", "..#..")
CROSS = ("#...#", ".#.#.", "..#..", ".#.#.", "#...#")
PLAY = ("#....", "##...", "###..", "##...", "#....")
CLOCK = (".###.", "#.#.#", "#.###", "#...#", ".###.")
SLASH = ("....#", "...#.", "..#..", ".#...", "#....")
ANGER = (".#.#.", "#...#", ".....", "#...#", ".#.#.")  # comic anger mark
NOTE = ("..##", "..#.", "..#.", "###.", "###.")
SEED_ART = ("##", "#.", "##")


# --- drawing helpers ----------------------------------------------------------

def runs_from_grid(grid, pens, off):
    """Rows of colour characters to (pen, col, row, length) runs; "." is empty."""
    runs = []
    for r, row in enumerate(grid):
        c, n = 0, len(row)
        while c < n:
            ch = row[c]
            if ch == ".":
                c += 1
                continue
            e = c + 1
            while e < n and row[e] == ch:
                e += 1
            runs.append((pens[ch], c - off, r, e - c))
            c = e
    return tuple(runs)


def blit(runs, x, y, s):
    x, y = int(x), int(y)
    for p, c, r, n in runs:
        display.set_pen(p)
        display.rectangle(x + c * s, y + r * s, n * s, s)


_art_runs = {}


def art_runs(art):
    """Horizontal runs of "#" in a small piece of pixel art, cached per art."""
    runs = _art_runs.get(id(art))
    if runs is None:
        runs = []
        for r, row in enumerate(art):
            c, n = 0, len(row)
            while c < n:
                if row[c] != "#":
                    c += 1
                    continue
                e = c + 1
                while e < n and row[e] == "#":
                    e += 1
                runs.append((c, r, e - c))
                c = e
        runs = tuple(runs)
        _art_runs[id(art)] = runs
    return runs


def draw_art(art, x, y, s, colour):
    display.set_pen(colour)
    x, y = int(x), int(y)
    for c, r, n in art_runs(art):
        display.rectangle(x + c * s, y + r * s, n * s, s)


def draw_bubble(text, x, y):
    """Speech bubble with a little tail."""
    w = display.measure_text(text, 2)
    display.set_pen(BALL_PEN)
    display.rectangle(x, y, w + 8, 22)
    display.rectangle(x + 4, y + 22, 4, 4)
    display.set_pen(EYE_PEN)
    display.text(text, x + 4, y + 4, -1, 2)


def draw_alert_sign(x, y):
    """Yellow sign with a "!"."""
    display.set_pen(ALERT_PEN)
    display.rectangle(x, y, 18, 22)
    display.set_pen(EYE_PEN)
    display.rectangle(x + 7, y + 4, 4, 9)
    display.rectangle(x + 7, y + 15, 4, 3)


def draw_degrees(text, x, y, scale, colour):
    """A number followed by a pixel degree sign."""
    display.set_pen(colour)
    display.text(text, x, y, -1, scale)
    dx = x + display.measure_text(text, scale) + scale
    display.rectangle(dx, y, 2 * scale, scale)
    display.rectangle(dx, y + 2 * scale, 2 * scale, scale)
    display.rectangle(dx, y, scale, 3 * scale)
    display.rectangle(dx + scale, y, scale, 3 * scale)
