# Messy, a pixel hamster: a little desk pet in the blocky, flat style of the
# Claude Code mascot. 240x240 (every pixel doubled), PICO-8 palette. Messy
# idles, looks around, walks, eats seeds, washes its face and falls asleep.
# Tap Messy (or Clawd) to make it happy, wake it up and see its name.
#
# Clawd, the Claude Code mascot, lives on the right. Now and then the two throw
# a ball to each other. A big pixel clock and the date sit in the background.
# When both are idle they also do things together: a fight with a dust cloud
# that ends in a hug, a chase around the world, a dance party, sharing a snack
# and leapfrog.
#
# Every few minutes a wannabe pirate (Guybrush fan art) walks in, shouts "BUH!"
# and scares both of them off the screen. They come back once he's gone.
#
# Clawd also shows the status of the coding agents in Herdr: the herdr-plugin/
# in this repo broadcasts it over UDP on every change. Working: Clawd types on
# a laptop. Blocked (waiting for you): "!" and blinking LEDs. Done: a green tick.
# Swipe left or right for a list of all agents and their status.
#
# The hamster runs the build pipeline: herdr-plugin/pipelines.py sends the
# state of develop and my merge requests. Running: the hamster runs in its
# wheel. Failed: the wheel stops, red sign, red LEDs. Green again: it cheers.
# The third page lists the pipelines.
#
# Home Assistant (ha_config.py, HA_TOKEN in secrets.py): the sky behind the
# clock shows the weather (sun, moon and stars, rain, snow, fog, lightning) and the fourth page "HOME" shows weather, rooms and low batteries.
# Both dress for the weather: a beanie when it freezes or snows, breath clouds
# when it's cold, umbrellas in the rain and sunglasses when it's hot.
#
# Sounds: different beeps when a pipeline starts, passes or fails, and a
# little pirate jingle when Guybrush walks in. The fifth page "SETTINGS"
# switches LEDs, sounds and music on and off (saved in settings.json).

import math
import random
import time

import json
import machine
import network
import ntptime
import socket

import tz
from presto import Buzzer, Presto

presto = Presto(ambient_light=False, full_res=False, layers=1)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()
touch = presto.touch
display.set_font("bitmap8")

for i in range(7):
    presto.set_led_rgb(i, 0, 0, 0)


def pen(rgb):
    return display.create_pen(*rgb)


# PICO-8 palette
BACKGROUND = pen((29, 43, 83))
SHADOW = pen((0, 84, 48))       # on grass
SNOW_SHADOW = pen((150, 162, 196))
COLOURS = {
    "#": pen((255, 163, 0)),    # fur
    "o": pen((255, 241, 232)),  # belly and face
    "p": pen((255, 119, 168)),  # ears, nose, paws, feet
    "e": pen((0, 0, 0)),        # eyes, mouth, seed, sunglasses
    "r": pen((255, 0, 77)),     # beanie
    "R": pen((126, 37, 83)),    # its stripes
}
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
CLOCK_PEN = pen((55, 75, 135))
DATE_PEN = pen((95, 110, 165))
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
GB_COLOURS = {  # Monkey Island 2 look: beard, marine coat, black trousers
    "H": pen((255, 240, 170)),  # hair highlight
    "y": pen((240, 200, 90)),   # hair
    "Y": pen((190, 140, 50)),   # hair shade
    "z": pen((170, 115, 50)),   # beard
    "k": pen((235, 180, 140)),  # skin
    "K": pen((190, 130, 100)),  # skin shade
    "w": pen((240, 235, 220)),  # shirt, eye white
    "L": pen((75, 100, 170)),   # coat light edge
    "c": pen((40, 60, 120)),    # marine blue coat
    "C": pen((25, 35, 80)),     # coat shade, far sleeve
    "g": pen((230, 180, 40)),   # gold buttons, buckle
    "b": pen((110, 60, 30)),    # belts
    "n": pen((30, 26, 36)),     # trousers, far leg
    "N": pen((62, 56, 74)),     # near leg
    "d": pen((80, 45, 25)),     # boots
    "e": pen((20, 15, 20)),     # eye, mouth
    # selective outline: a darker shade of whatever it borders
    "j": pen((125, 85, 30)),    # around hair and beard
    "q": pen((150, 95, 70)),    # around skin
    "v": pen((14, 20, 52)),     # around the coat
    "O": pen((12, 8, 18)),      # around trousers
    "D": pen((48, 26, 14)),     # around boots
}
OUTLINE_OF = {"H": "j", "y": "j", "Y": "j", "z": "j", "k": "q", "K": "q", "w": "v", "L": "v", "c": "v",
              "C": "v", "g": "v", "b": "v", "n": "O", "N": "O", "d": "D", "e": "O"}

S = 4  # size of one hamster pixel
GROUND = 206
BASE_Y = GROUND - 14 * S  # sprite top when standing: 13 body rows + feet row
MIN_X = 4  # the hamster lives on the left, Clawd on the right
MAX_X = 60

CS = 5  # size of one Clawd pixel
C_BASE_Y = GROUND - 10 * CS
C_MIN_X = 124
C_MAX_X = WIDTH - 16 * CS - 4

# 16x13, eyes are drawn separately
BODY = (
    "..##........##..",
    ".#pp#......#pp#.",
    ".#p##########p#.",
    "..############..",
    ".##############.",
    "################",
    "################",
    "##oooooppooooo##",
    "#oooooooooooooo#",
    "#oooooooooooooo#",
    "##oooooooooooo##",
    ".##oooooooooo##.",
    "..############..",
)
BODY_PIXELS = [(c, r, ch) for r, row in enumerate(BODY) for c, ch in enumerate(row) if ch != "."]

EYES = {
    "open": ((4, 5), (4, 6), (11, 5), (11, 6)),
    "closed": ((3, 6), (4, 6), (11, 6), (12, 6)),
    "happy": ((3, 6), (4, 5), (5, 6), (10, 6), (11, 5), (12, 6)),
    "wide": ((4, 5), (5, 5), (4, 6), (5, 6), (10, 5), (11, 5), (10, 6), (11, 6)),
    "angry": ((3, 5), (4, 6), (5, 6), (12, 5), (11, 6), (10, 6)),
}
SEED = ("ee", "eo", "ee")
HEART = (".#.#.", "#####", "#####", ".###.", "..#..")
ZED = ("####", "..#.", ".#..", "####")
SPARK = (".#.", "###", ".#.")
SPARK_X = ("#.#", ".#.", "#.#")
TICK = ("....#", "...##", "#.##.", "###..", ".#...")
EXCL = ("..#..", ".###.", ".###.", "..#..", ".....", "..#..")
QMARK = (".###.", "#...#", "...#.", "..#..", ".....", "..#..")
RING = (".###.", "#...#", "#...#", "#...#", ".###.")
GEAR_A = ("#.#.#", ".###.", "##.##", ".###.", "#.#.#")
GEAR_B = ("..#..", "#####", "##.##", "#####", "..#..")
CROSS = ("#...#", ".#.#.", "..#..", ".#.#.", "#...#")
PLAY = ("#....", "##...", "###..", "##...", "#....")
CLOCK = (".###.", "#.#.#", "#.###", "#...#", ".###.")
SLASH = ("....#", "...#.", "..#..", ".#...", "#....")
ANGER = (".#.#.", "#...#", ".....", "#...#", ".#.#.")  # comic anger mark
NOTE = ("..##", "..#.", "..#.", "###.", "###.")
MINI_HAMSTER = (".#....#.", "########", "##.##.##", "########", ".######.")
MINI_CLAWD = (".######.", ".#.##.#.", "########", ".######.", ".#.#.#.#")
BALL = (".ww.", "rrrr", "wwww", ".ww.")  # 4x4, drawn with 4px pixels

# Clawd, after the Claude Code logo (" ▐▛███▜▌ / ▝▜█████▛▘ / ▘▘ ▝▝") with every
# block quadrant as one pixel, doubled in height: 16x10, a 12x8 body with
# arms on rows 4-5, four legs on rows 8-9. Eyes as (col, row, w, h).
CLAWD_EYES = {
    "open": ((4, 2, 1, 2), (11, 2, 1, 2)),
    "closed": ((3, 3, 2, 1), (11, 3, 2, 1)),
    "happy": ((3, 3, 1, 1), (4, 2, 1, 1), (5, 3, 1, 1), (10, 3, 1, 1), (11, 2, 1, 1), (12, 3, 1, 1)),
    "wide": ((4, 2, 2, 2), (10, 2, 2, 2)),
    "sad": ((4, 3, 1, 1), (11, 3, 1, 1)),
    "down": ((4, 3, 1, 1), (11, 3, 1, 1)),
    "angry": ((3, 1, 1, 1), (4, 2, 1, 2), (12, 1, 1, 1), (11, 2, 1, 2)),
}



# Building a sprite pixel by pixel is slow in MicroPython (a dict with a few
# hundred entries takes ~100 ms here), so every pose is built once into a grid,
# turned into horizontal runs of one colour and cached. Drawing a cached pose is
# just a handful of rectangles.

def runs_from_grid(grid, pens, off):
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


_h_cache = {}


def hamster_sprite(eyes, look, step, bob, puff, paws, mouth, blush, seed, ear, sniff, wear=""):
    key = (eyes, look, step, bob, puff, paws, mouth, blush, seed, ear, sniff, wear)
    runs = _h_cache.get(key)
    if runs is not None:
        return runs
    g = [["."] * 18 for _ in range(14)]  # cols -1..16

    def put(c, r, ch):
        if 0 <= r < 14 and -1 <= c <= 16:
            g[r][c + 1] = ch

    for c, r, ch in BODY_PIXELS:
        put(c, r + bob, ch)
    if ear:  # left ear flicks outwards
        put(2, bob, ".")
        put(3, bob, ".")
        put(1, bob, "#")
        put(2, bob, "#")
    if sniff:  # nose twitches up
        put(7, 7 + bob, "o")
        put(8, 7 + bob, "o")
        put(7, 6 + bob, "p")
        put(8, 6 + bob, "p")
    for c, r in EYES[eyes]:
        put(c + (look if eyes == "open" else 0), r + bob, "e")
    if blush:
        put(2, 7 + bob, "p")
        put(13, 7 + bob, "p")
    if mouth:
        put(6 + mouth, 8 + bob, "e")
    for r in range(8, 9 + puff) if puff else ():  # full cheeks bulge out
        put(-1, r + bob, "#")
        put(16, r + bob, "#")
        put(0, r + bob, "o")
        put(15, r + bob, "o")
    if seed:
        for r, row in enumerate(SEED):
            for c, ch in enumerate(row):
                put(7 + c, 9 + r + bob, ch)
    if "hat" in wear:  # beanie with a bobble instead of the ears
        for r in range(3):
            for c in range(-1, 17):
                put(c, r + bob, ".")
        put(7, bob, "o")
        put(8, bob, "o")
        for c in range(4, 12):
            put(c, 1 + bob, "r" if c % 3 else "R")
        for c in range(3, 13):
            put(c, 2 + bob, "r")
        for c in range(2, 14):
            put(c, 3 + bob, "o")
    if "shades" in wear:
        for c in (3, 4, 5, 10, 11, 12):
            put(c, 5 + bob, "e")
            put(c, 6 + bob, "e")
        for c in range(6, 10):
            put(c, 5 + bob, "e")
    for c, r in paws:
        put(c, r + bob, "p")
    # Feet: step 1 lifts the left one, step 2 the right one
    for c in (3, 4):
        put(c, 12 if step == 1 else 13, "p")
    for c in (11, 12):
        put(c, 12 if step == 2 else 13, "p")
    runs = runs_from_grid(g, COLOURS, 1)
    if len(_h_cache) > 200:
        _h_cache.clear()
    _h_cache[key] = runs
    return runs


def draw_hamster(x, y, eyes="open", look=0, step=0, bob=0, puff=0, paws=(), mouth=0, blush=False, seed=False,
                 ear=False, sniff=False, wear=""):
    blit(hamster_sprite(eyes, look, step, bob, puff, paws, mouth, blush, seed, ear, sniff, wear), x, y, S)


def draw_clawd(x, y, eyes="open", look=0, bob=0, step=0, arms=(False, False), laptop=False, wear=""):
    """arms: per side True (up), False (down) or a row number."""
    x, y = int(x), int(y)

    def px(c, r, w=1, h=1):
        display.rectangle(x + c * CS, y + r * CS, w * CS, h * CS)

    display.set_pen(CLAWD_PEN)
    px(2, bob, 12, 8)
    for side, a in zip((0, 14), arms):
        px(side, (2 if a is True else 4 if a is False else a) + bob, 2, 2)
    # Legs: step 1 lifts the outer pair, step 2 the inner pair; bob squashes them
    for i, c in enumerate((3, 5, 10, 12)):
        if bob:
            px(c, 9)
        else:
            px(c, 8, 1, 1 if step == 1 + (i in (1, 2)) else 2)
    display.set_pen(EYE_PEN)
    for c, r, w, h in CLAWD_EYES[eyes]:
        px(c + (look if eyes == "open" else 0), r + bob, w, h)
    if "hat" in wear:
        display.set_pen(HAT_PEN)
        px(4, bob - 2, 8, 1)
        px(3, bob - 1, 10, 1)
        display.set_pen(WOOL_PEN)
        px(2, bob, 12, 1)
        px(7, bob - 3, 2, 1)
    if "shades" in wear:
        display.set_pen(EYE_PEN)
        px(3, 2 + bob, 3, 2)
        px(10, 2 + bob, 3, 2)
        px(6, 2 + bob, 4, 1)
    if laptop:  # lid facing us, keyboard base in front of the legs
        display.set_pen(LAPTOP_PEN)
        px(4, 4, 8, 4)
        display.set_pen(LAPTOP_EDGE_PEN)
        px(3, 8, 10, 1)
        px(7, 5, 2, 2)  # logo


# Guybrush fan art in the style of Monkey Island 2 (beard, long marine coat,
# bandolier and belt), facing right. 16 wide: 25 rows of body plus 7 rows of
# legs; a dark outline is added around the whole figure when a pose is built.
GB = 4  # size of one pirate pixel
GB_W = 16
GB_BODY = (
    "......yyyy......",
    "....yyHHHyy.....",
    "...yyyyyyyyyy...",
    "..yYyyyyyyyyy...",
    "..Yyyyyykkkkk...",
    "..YYyyykkkkkk...",
    "..bYyyKkkwekkk..",
    ".yY.yyKkkkkkkkk.",
    ".yY..zkkkkkKkk..",
    ".Yy..zzkkkzzk...",
    ".yY..zzzzzzzz...",
    "..Y...zzzzzz....",
    "..y....kkk......",
    "...Y.cCwwwCc....",
    "....Lccwwwccc...",
    "...CLcccwccbcC..",
    "...CLcccccbccC..",
    "...CLccccbcgcC..",
    "...CLcccbccccC..",
    "...CLccbcccgcC..",
    "...CLcbccccccC..",
    "...CbbbbgbbbbC..",
    "...kLcccccccck..",
    "...CLcccc.ccccC.",
    "..CLccc....cccC.",
)
# Walk cycle: a (far leg back), pass, b (far leg forward), pass
GB_LEGS = {
    "stand": (".....nn..NN.....", ".....nn..NN.....", ".....nn..NN.....", ".....nn..NN.....",
              ".....dd..dd.....", "....ddd..ddd....", "....dddd.dddd..."),
    "a": ("......nNN.......", ".....nn..NN.....", "....nn....NN....", "...nn......NN...",
          "...dd.......dd..", "..ddd.......ddd.", "..dddd......dddd"),
    "pass": ("......nNN.......", "......nNN.......", "......nNN.......", "......nNN.......",
             "......ddd.......", ".....dddd.......", ".....ddddd......"),
    "b": ("......NNn.......", ".....NN..nn.....", "....NN....nn....", "...NN......nn...",
          "...dd.......dd..", "..ddd.......ddd.", "..dddd......dddd"),
}
# Arm swing while walking: lower sleeves (rows 19-22) of the far arm (col 3)
# and the near arm (col 13) swing back and forth
GB_SWING = {
    "a": ((2, 19, "C"), (2, 20, "C"), (1, 21, "C"), (1, 22, "k"),
          (14, 19, "c"), (14, 20, "c"), (15, 21, "c"), (15, 22, "k")),
    "b": ((12, 19, "c"), (11, 20, "c"), (11, 21, "c"), (10, 22, "k")),
}
GB_WALK = (("a", "a", 0), ("pass", "down", -2), ("b", "b", 0), ("pass", "down", -2))  # legs, arms, bob
# Arms thrown up in a V: the sleeves (cols 3 and 13, rows 14-22) move up here
GB_ARMS_UP = (
    (2, 13, "C"), (3, 13, "c"), (1, 12, "C"), (2, 12, "c"), (0, 11, "C"), (1, 11, "c"),
    (-1, 10, "C"), (0, 10, "c"), (-1, 9, "k"), (0, 9, "k"), (-1, 8, "k"), (0, 8, "k"),
    (12, 13, "c"), (13, 13, "C"), (13, 12, "c"), (14, 12, "C"), (14, 11, "c"), (15, 11, "C"),
    (15, 10, "c"), (16, 10, "C"), (15, 9, "k"), (16, 9, "k"), (15, 8, "k"), (16, 8, "k"),
)
GB_MOUTH = (11, 10)
GB_Y = GROUND - 32 * GB
GB_OFF = 3  # grid columns left of col 0 (arms and outline reach out to -2 / 17)


_gb_cache = {}


def guybrush_sprite(flip, legs, arms, mouth):
    key = (flip, legs, arms, mouth)
    runs = _gb_cache.get(key)
    if runs is not None:
        return runs
    cols = GB_W + 2 * GB_OFF
    g = [["."] * cols for _ in range(32)]

    def put(c, r, ch):
        if 0 <= r < 32 and 0 <= c + GB_OFF < cols:
            g[r][c + GB_OFF] = ch

    for r, row in enumerate(GB_BODY + GB_LEGS[legs]):
        for c, ch in enumerate(row):
            if ch != ".":
                put(c, r, ch)
    if arms == "up":
        for r in range(14, 23):
            put(3, r, ".")
            put(13, r, ".")
        put(4, 22, "L")  # coat edge where the hand was
        for c, r, ch in GB_ARMS_UP:
            put(c, r, ch)
    elif arms in GB_SWING:
        for r in range(19, 23):
            put(3, r, ".")
            put(13, r, ".")
        for c, r, ch in GB_SWING[arms]:
            put(c, r, ch)
    if mouth:
        put(GB_MOUTH[0], GB_MOUTH[1], "e")
    # selective outline: each outline pixel is a dark shade of its neighbour
    src = [row[:] for row in g]
    for r in range(32):
        for c in range(cols):
            if src[r][c] != ".":
                continue
            for rr, cc in ((r, c - 1), (r, c + 1), (r + 1, c), (r - 1, c)):
                if 0 <= rr < 32 and 0 <= cc < cols and src[rr][cc] != ".":
                    g[r][c] = OUTLINE_OF.get(src[rr][cc], "O")
                    break
    if flip:
        for row in g:
            row.reverse()
    # unflipped: draw col = index - GB_OFF; flipped: index j shows col GB_W-1-c
    # with c = cols-1-j-GB_OFF, which works out to the same offset
    runs = runs_from_grid(g, GB_COLOURS, GB_OFF)
    _gb_cache[key] = runs
    return runs


def draw_guybrush(gx, flip=False, legs="stand", arms="down", mouth=False, bob=0):
    blit(guybrush_sprite(flip, legs, arms, mouth), gx, GB_Y + bob, GB)


def draw_bubble(text, x, y):
    w = display.measure_text(text, 2)
    display.set_pen(BALL_PEN)
    display.rectangle(x, y, w + 8, 22)
    display.rectangle(x + 4, y + 22, 4, 4)  # little tail
    display.set_pen(EYE_PEN)
    display.text(text, x + 4, y + 4, -1, 2)


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


sky_pen = None  # set per frame from the weather: night sky, lightning flash

# Ground: a strip of pixel meadow (4 px blocks) that follows the seasons:
# spring flowers, lush summer grass, autumn leaves, frosty winter grass, and
# covered in snow when it snows. Grass on top, soil with pebbles below.
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
_floor = {}


def season():
    m = tz.localtime()[1] if clock_synced else 6
    return ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer",
            "autumn", "autumn", "autumn", "winter")[m - 1]


def floor_runs(snow, sea):
    key = (snow, sea)
    runs = _floor.get(key)
    if runs is not None:
        return runs
    cols = WIDTH // 4
    seed = [12345]

    def rnd(n):
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
    _floor[key] = runs
    return runs


def draw_scene(shadows):
    display.set_pen(sky_pen or BACKGROUND)
    display.clear()
    cond = weather()[0] if HA_TOKEN else None
    snow = cond in ("snowy", "snowy-rainy")
    blit(floor_runs(snow, season()), 0, GROUND - 4, 4)
    # Shadows shrink while their owner is in the air
    display.set_pen(SNOW_SHADOW if snow else SHADOW)
    for cx, w in shadows:
        w = max(4, int(w))
        display.rectangle(int(cx) - w // 2, GROUND, w, 4)


# Background clock: 3x5 pixel digits drawn with 10 px blocks, date above
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
clock_next_sync = 0


def sync_clock(now):
    """Set the RTC from NTP once WiFi is up; retry every minute until it works."""
    global clock_synced, clock_next_sync
    if clock_synced or time.ticks_diff(now, clock_next_sync) < 0 or not wlan.isconnected():
        return
    clock_next_sync = time.ticks_add(now, 60000)
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
    left = 46 if HA_TOKEN and ha and ha.states.get(HAC.WEATHER) else 8
    date = "%s %d.%d." % (WEEKDAYS[t[6]], t[2], t[1])
    if display.measure_text(date, 2) > WIDTH - left - 6:
        date = "%s %d.%d." % (WEEKDAYS[t[6]][:2], t[2], t[1])
    dw = display.measure_text(date, 2)
    display.set_pen(DATE_PEN)
    display.text(date, max(left, (WIDTH - dw) // 2), 12, -1, 2)


# --- backlight -------------------------------------------------------------
# The 7 RGB LEDs on the back glow on the wall and follow the hamster's mood.
# Colours fade smoothly towards the target of the current state.

led = [0.0, 0.0, 0.0]
shown_led = None


def led_target(state, t):
    wave = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 3000)
    if state == "sleep":  # dim moonlight, slow breathing
        return (4 + 6 * wave, 4 + 6 * wave, 20 + 30 * wave)
    if state == "happy":  # pink pulse on every hop
        hop = math.sin(math.pi * ((t % 700) / 700))
        return (60 + 140 * hop, 10 + 30 * hop, 40 + 70 * hop)
    if state == "startle":
        return (160, 160, 160) if t < 150 else (40, 30, 10)
    if state == "ball":  # Claude coral while they play
        return (70 + 15 * wave, 30, 15)
    if state == "eat":  # cosy warm flicker while munching
        return (90 + 30 * ((t // 150) % 2), 40, 5)
    if state == "brawl":  # fight cloud: red/white flicker
        return (230, 40, 20) if (t // 90) % 2 else (230, 210, 190)
    if state == "dance":  # party colours
        return (90 + 90 * math.sin(t / 300), 90 + 90 * math.sin(t / 300 + 2.1), 90 + 90 * math.sin(t / 300 + 4.2))
    if state == "failed":  # a pipeline is red: slow red pulse
        return (40 + 120 * wave, 0, 8 + 10 * wave)
    if state == "alert":  # an agent is waiting for you: blink
        return (220, 130, 0) if (t // 400) % 2 == 0 else (15, 8, 0)
    if state == "done":
        return (15, 80 + 30 * wave, 25)
    return (50 + 15 * wave, 25 + 8 * wave, 4)  # warm amber


def update_leds(state, t):
    global shown_led
    if state is None:  # switched off
        if shown_led != (0, 0, 0):
            for i in range(7):
                presto.set_led_rgb(i, 0, 0, 0)
            shown_led = (0, 0, 0)
        return
    target = led_target(state, t)
    speed = 0.5 if state in ("happy", "startle", "alert", "brawl", "dance") else 0.08
    for i in range(3):
        led[i] += (target[i] - led[i]) * speed
    rgb = tuple(int(c) for c in led)
    if rgb != shown_led:
        for i in range(7):
            presto.set_led_rgb(i, *rgb)
        shown_led = rgb


# --- sounds ----------------------------------------------------------------
# Notes are (start Hz, end Hz, ms); the pitch slides from start to end, 0 is a
# pause. A 10 ms timer plays them in the background so drawing never waits.

CHARACTER_SOUNDS = False  # squeaks and munching; too much for a desk, so off
VOLUME = 0.1  # PWM duty, 0.5 is the loudest
MUSIC_VOLUME = 0.08

# Settings page: saved to flash only when something is switched
SETTINGS_FILE = "settings.json"
settings = {"leds": True, "anim_leds": True, "sounds": True, "anim": True, "music": True}
try:
    with open(SETTINGS_FILE) as f:
        settings.update(json.load(f))
except (OSError, ValueError):
    pass


def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except OSError:
        pass


SOUNDS = {
    "squeak": ((1800, 2600, 60), (0, 0, 40), (2000, 3200, 80)),
    "startle": ((1400, 3400, 120), (0, 0, 30), (3000, 2600, 40)),
    "whistle": ((2600, 1200, 800),),
    "catch": ((900, 1500, 40),),
    "munch": ((420, 300, 25),),
    "yum": ((1200, 1600, 70), (0, 0, 30), (1500, 2100, 90)),
    "yawn": ((900, 1100, 120), (1100, 450, 450)),
    "snore": ((160, 130, 280),),
    "step": ((3500, 3500, 6),),
    "toss": ((600, 1400, 60),),
    # pipelines: two rising beeps, a happy run up, a sad trombone
    "pipe_start": ((880, 880, 70), (0, 0, 50), (1175, 1175, 90)),
    "pipe_ok": ((784, 784, 90), (0, 0, 20), (988, 988, 90), (0, 0, 20), (1175, 1175, 90), (0, 0, 20),
                (1568, 1568, 240)),
    "pipe_fail": ((523, 523, 180), (0, 0, 40), (494, 494, 180), (0, 0, 40), (466, 466, 180), (0, 0, 40),
                  (440, 440, 160), (415, 370, 520)),
    "click": ((1800, 1800, 15),),
    # Claude: a soft ding-dong when it's done, three quick beeps when it needs you
    "agent_done": ((1319, 1319, 80), (0, 0, 30), (1047, 1047, 160)),
    "agent_alert": ((1760, 1760, 60), (0, 0, 60), (1760, 1760, 60), (0, 0, 60), (1760, 1760, 60)),
    # fight: growls, punches, a whoosh when they fly apart, an aww for the hug
    "grr": ((150, 120, 160),),
    "pow": ((320, 70, 70),),
    "bam": ((950, 140, 90),),
    "bonk": ((600, 1300, 40), (1300, 280, 90)),
    "whoosh": ((2200, 500, 220),),
    "aww": ((660, 880, 120), (0, 0, 30), (880, 1047, 180)),
}
PIPE_SOUNDS = ("pipe_start", "pipe_ok", "pipe_fail", "click", "agent_done", "agent_alert")  # SOUNDS switch
FIGHT_SOUNDS = ("grr", "pow", "bam", "bonk", "whoosh", "aww")  # ANIMATION switch (scene sounds)

# Original pirate jingle (not the game's theme): (Hz, ms), 0 is a rest
PIRATE_JINGLE = (
    (392, 150), (523, 300), (523, 150), (587, 150), (659, 150), (698, 150), (784, 450), (0, 150),
    (659, 150), (587, 150), (523, 300), (659, 150), (587, 450), (0, 150),
    (392, 150), (523, 300), (523, 150), (587, 150), (659, 150), (698, 150), (784, 300), (880, 150), (784, 300),
    (698, 150), (659, 150), (587, 300), (494, 150), (523, 600),
)

buzzer = Buzzer(43)
notes = []
note_ms = 0


def stop_music():
    global notes, music_playing
    if music_playing:
        notes = []
        buzzer.set_tone(0)
        music_playing = False


def play(name, volume=VOLUME):
    global notes, note_ms, music_playing
    if name in PIPE_SOUNDS:
        allowed = settings["sounds"]
    elif name in FIGHT_SOUNDS:
        allowed = settings["anim"]
    else:
        allowed = CHARACTER_SOUNDS
    if not allowed:
        return
    notes = [(f0, f1, ms, volume) for f0, f1, ms in SOUNDS[name]]
    note_ms = 0
    music_playing = False


RTTTL_NOTES = {"c": 0, "c#": 1, "d": 2, "d#": 3, "e": 4, "f": 5, "f#": 6, "g": 7, "g#": 8, "a": 9, "a#": 10, "b": 11}


def parse_rtttl(text):
    """RTTTL ringtone ("name:d=4,o=5,b=120:8e6,8p,...") to [(Hz, ms), ...]."""
    parts = text.strip().split(":")
    if len(parts) < 3:
        return None
    defaults = {"d": 4, "o": 6, "b": 63}
    for item in parts[1].split(","):
        key, _, value = item.strip().partition("=")
        if key in defaults and value.isdigit():
            defaults[key] = int(value)
    whole = 4 * 60000 // defaults["b"]  # ms of a whole note
    tune = []
    for token in ":".join(parts[2:]).split(","):
        t = token.strip().lower()
        if not t:
            continue
        i = 0
        while i < len(t) and t[i].isdigit():
            i += 1
        dur = int(t[:i]) if i else defaults["d"]
        name = t[i] if i < len(t) else "p"
        i += 1
        if i < len(t) and t[i] == "#":
            name += "#"
            i += 1
        dotted = "." in t[i:]
        digits = "".join(ch for ch in t[i:] if ch.isdigit())
        octave = int(digits) if digits else defaults["o"]
        ms = whole // dur
        if dotted:
            ms += ms // 2
        if name == "p" or name not in RTTTL_NOTES:
            tune.append((0, ms))
        else:
            n = RTTTL_NOTES[name] + 12 * (octave - 4)
            tune.append((int(261.63 * 2 ** (n / 12)), ms))
    return tune or None


def load_rtttl(name):
    """(tune, beat ms) from an RTTTL file on the Presto, or (None, None)."""
    try:
        with open(name) as f:
            text = f.read()
    except OSError:
        return None, None
    tune = parse_rtttl(text)
    bpm = 63
    for item in text.split(":")[1].split(",") if text.count(":") >= 2 else ():
        key, _, value = item.strip().partition("=")
        if key == "b" and value.isdigit():
            bpm = int(value)
    return tune, 60000 // bpm


def guybrush_tune():
    """Your own melody from guybrush.rtttl on the Presto, else the jingle."""
    try:
        with open("guybrush.rtttl") as f:
            return parse_rtttl(f.read()) or PIRATE_JINGLE
    except OSError:
        return PIRATE_JINGLE


music_playing = False


def play_music(tune):
    """Songs only play while the scene is on screen."""
    global notes, note_ms, music_playing
    if not settings["music"] or view != "scene":
        return
    music_playing = True
    notes = []
    for f, ms in tune:  # a short gap between notes so repeated ones are heard
        notes.append((f, f, ms - 25, MUSIC_VOLUME))
        notes.append((0, 0, 25, 0))
    note_ms = 0


def _sound_tick(_):
    global notes, note_ms
    if not notes:
        return
    f0, f1, ms, volume = notes[0]
    if note_ms >= ms:
        notes.pop(0)
        note_ms = 0
        if not notes:
            buzzer.set_tone(0)
        return
    if f0:
        buzzer.set_tone(int(f0 + (f1 - f0) * note_ms / ms), volume)
    else:
        buzzer.set_tone(0)
    note_ms += 10


buzzer.set_tone(0)
sound_timer = machine.Timer(period=10, callback=_sound_tick)


# --- agent status from Herdr ------------------------------------------------
# herdr-plugin/notify.py sends {"status": "working", ...} to UDP port 47474 on
# every change. Without updates the status fades out after a while, in case
# the PC went away.

AGENT_PORT = 47474
AGENT_STALE_MS = 45 * 60 * 1000
CLAWD_FOR = {"working": "work", "blocked": "alert", "done": "done"}

agent_status = None
agent_list = []
agent_rx = 0
pipe_status = None  # running, failed, success
pipe_items = []
pipe_rx = 0
PIPE_STALE_MS = 3 * 60 * 1000  # the bridge sends every 30 s
agent_sock = None
wlan = network.WLAN(network.STA_IF)
try:
    from secrets import WIFI_PASSWORD, WIFI_SSID
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
except Exception:
    pass


agent_seen = {}  # (workspace, kind) -> last status, for the beeps
agent_beep = None  # "done" or "alert", played by the main loop


def watch_agents(entries):
    """Beep when one agent finishes or asks something, even while another
    one keeps working (the combined status wouldn't change then)."""
    global agent_seen, agent_beep
    seen = {}
    for a in entries:
        key = (a.get("w"), a.get("k"))
        s, before = a.get("s"), agent_seen.get(key)
        seen[key] = s
        if before is None or s == before:
            continue
        if s == "blocked":
            agent_beep = "alert"
        elif before == "working" and s in ("done", "idle") and agent_beep != "alert":
            agent_beep = "done"
    agent_seen = seen


pipe_seen = {}  # (space, MR or branch) -> last status, for the beeps
pipe_beep = None  # "pipe_start", "pipe_ok" or "pipe_fail", played by the main loop
WAITING_STATES = ("running", "pending", "created", "preparing", "waiting_for_resource", "scheduled")


def watch_pipes(items):
    """Beep for each pipeline on its own, also while others keep running."""
    global pipe_seen, pipe_beep
    seen = {}
    for it in items:
        key = (it.get("w"), it.get("n"))
        s, before = it.get("s"), pipe_seen.get(key)
        seen[key] = s
        if before is None or s == before:
            continue
        if s == "failed":
            pipe_beep = "pipe_fail"  # the most important one wins
        elif s == "success" and before in WAITING_STATES and pipe_beep != "pipe_fail":
            pipe_beep = "pipe_ok"
        elif s in WAITING_STATES and before not in WAITING_STATES and not pipe_beep:
            pipe_beep = "pipe_start"
    pipe_seen = seen


def poll_agent(now):
    global agent_status, agent_list, agent_rx, agent_sock, pipe_status, pipe_items, pipe_rx
    if agent_sock is None:
        if not wlan.isconnected():
            return
        try:
            agent_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            agent_sock.bind(("0.0.0.0", AGENT_PORT))
            agent_sock.setblocking(False)
        except OSError:
            agent_sock = None
            return
    while True:
        try:
            data = agent_sock.recv(4096)  # pipeline lists are ~1 KB
        except OSError:
            break
        try:
            msg = json.loads(data)
            if msg.get("type") == "pipelines":
                pipe_status = msg["status"] if msg["status"] != "none" else None
                pipe_items = msg.get("items", [])
                watch_pipes(pipe_items)
                pipe_rx = now
                continue
            agent_status = msg["status"]
            new_list = msg.get("list", [])
            watch_agents(new_list)
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


STATUS_PEN = {"working": CLAWD_PEN, "blocked": ALERT_PEN, "done": TICK_PEN, "idle": IDLE_PEN}


def draw_panel(x, y, w, h, hi=None):
    """Bevelled pixel tile: light top/left edge, dark bottom/right edge."""
    display.set_pen(PANEL_LO_PEN)
    display.rectangle(x, y, w, h)
    display.set_pen(hi or PANEL_HI_PEN)
    display.rectangle(x, y, w - 3, h - 3)
    display.set_pen(PANEL_PEN)
    display.rectangle(x + 3, y + 3, w - 6, h - 6)


VIEWS = ("scene", "agents", "pipelines", "home", "settings")


def draw_page_dots(page):
    x0 = WIDTH // 2 - (len(VIEWS) * 12 - 6) // 2
    for i in range(len(VIEWS)):
        display.set_pen(TEXT_PEN if i == page else DIM_PEN)
        display.rectangle(x0 + i * 12, HEIGHT - 8, 6, 6)


# Hamster wheel: rim blocks at fixed spots (pixel-stable), the rotation is
# shown by colours moving along the rim and by turning spokes
WHEEL_R = 46
WHEEL_CY = GROUND - WHEEL_R - 4
WHEEL_RIM = [(int(WHEEL_R * math.cos(i * math.pi / 15)), int(WHEEL_R * math.sin(i * math.pi / 15))) for i in range(30)]
WHEEL_LIFT = 8  # the hamster runs on the inside of the rim, a bit above the floor


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


PROGRESS_PEN = pen((41, 173, 255))
PROGRESS_DARK_PEN = pen((20, 110, 190))
RIM_TOP = len(WHEEL_RIM) * 3 // 4  # rim block at 12 o'clock


def progress():
    """Share of jobs done (0..1) of the first running pipeline, or None."""
    for it in pipe_items:
        if it.get("s") == "running" and "/" in it.get("p", ""):
            done, total = (int(v) for v in it["p"].split("/"))
            return done / total if total else None
    return None


def draw_wheel_rim(cx, shift, broken):
    """The rim fills up in blue, clockwise from the top, as the
    pipeline's jobs finish; the rest shows the wheel turning."""
    n = len(WHEEL_RIM)
    frac = None if broken else progress()
    filled = int(frac * n + 0.5) if frac is not None else 0
    for i, (dx, dy) in enumerate(WHEEL_RIM):
        if broken:
            display.set_pen(FAIL_PEN if i % 5 == 0 else WHEEL_DARK_PEN)
        elif (i - RIM_TOP) % n < filled:
            display.set_pen(PROGRESS_DARK_PEN if (i + shift) % 3 == 0 else PROGRESS_PEN)
        else:
            display.set_pen(WHEEL_DARK_PEN if (i + shift) % 3 == 0 else WHEEL_PEN)
        display.rectangle(cx + dx - 4, WHEEL_CY + dy - 4, 8, 8)


PIPE_PEN = {"running": COLOURS["#"], "pending": WHEEL_PEN, "created": WHEEL_PEN, "failed": FAIL_PEN,
            "success": TICK_PEN, "manual": MANUAL_PEN}


PIPE_WORD = {"running": "RUNNING", "pending": "QUEUED", "created": "QUEUED", "scheduled": "QUEUED",
             "waiting_for_resource": "QUEUED", "preparing": "QUEUED", "failed": "FAILED",
             "success": "PASSED", "manual": "MANUAL", "canceled": "CANCELED", "skipped": "SKIPPED"}
WAITING = ("pending", "created", "scheduled", "waiting_for_resource", "preparing")


def shorten(text, n):
    """Cut at a word boundary and mark it with '..'."""
    if len(text) <= n:
        return text
    cut = text[:n - 2]
    if " " in cut[n // 2:]:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" :-,") + ".."


def draw_pipelines(now):
    display.set_pen(BACKGROUND)
    display.clear()
    draw_art(MINI_HAMSTER, 10, 9, 3, COLOURS["#"])
    display.set_pen(TEXT_PEN)
    display.text("PIPELINES", 42, 10, -1, 2)
    if not pipe_items:
        display.set_pen(DIM_PEN)
        if pipe_rx and time.ticks_diff(now, pipe_rx) < PIPE_STALE_MS:
            display.text("All quiet: no pipelines in your spaces", 12, 60, WIDTH - 24, 2)
        else:
            display.text("Waiting for GitLab...", 12, 60, WIDTH - 24, 2)
            display.text("Herdr plugin: pipelines-start", 12, 100, -1, 1)
        draw_page_dots(2)
        return
    # Group rows by space (keeping the urgency order inside); with a single
    # space its name goes into the header instead
    spaces = []
    for it in pipe_items:
        if it.get("w", "") not in spaces:
            spaces.append(it.get("w", ""))
    rows = [it for sp in spaces for it in pipe_items if it.get("w", "") == sp]
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
            display.set_pen(DIM_PEN)
            display.text(last_space.upper(), 10, y + 1, -1, 1)
            display.rectangle(14 + display.measure_text(last_space.upper(), 1), y + 4, WIDTH - 28 - display.measure_text(last_space.upper(), 1), 1)
            y += 11
        if y + 34 > HEIGHT - 10:
            break
        st = it.get("s", "")
        colour = PIPE_PEN.get(st, IDLE_PEN)
        draw_panel(6, y, WIDTH - 12, 32, FAIL_PEN if st == "failed" and blink else None)
        display.set_pen(colour)
        display.rectangle(9, y + 3, 3, 26)
        ix, iy = 17, y + 8
        if st == "running":
            draw_art(GEAR_A if (now // 200) % 2 else GEAR_B, ix, iy, 3, colour)
        elif st == "failed":
            draw_art(CROSS, ix, iy, 3, colour)
        elif st == "success":
            draw_art(TICK, ix, iy, 3, colour)
        elif st == "manual":
            draw_art(PLAY, ix + 2, iy, 3, colour)
        elif st in WAITING:
            draw_art(CLOCK, ix, iy, 3, colour)
        else:
            draw_art(SLASH, ix, iy, 3, colour)
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
    draw_page_dots(2)


# --- Home Assistant ----------------------------------------------------------

try:
    from secrets import HA_TOKEN
    import ha_config as HAC
    from haclient import HAClient
except ImportError:
    HA_TOKEN = None
ha = None

FLASH_PEN = pen((150, 160, 200))
DARK_CLOUD_PEN = pen((55, 60, 90))
RAIN_PEN = pen((90, 140, 220))
SNOW_PEN = pen((230, 235, 245))
FOG_PEN = pen((60, 72, 110))
SUN_PEN = pen((255, 210, 60))
MOON_PEN = pen((230, 230, 200))
STAR_PEN = pen((200, 200, 230))
FLAME_PEN = pen((255, 120, 30))
BULB_OFF_PEN = pen((70, 70, 90))

SUN_ART = ("#..#..#", ".#####.", ".#####.", "#######", ".#####.", ".#####.", "#..#..#")
SUN_ART_B = ("...#...", ".#####.", ".#####.", "#######", ".#####.", ".#####.", "...#...")
MOON_ART = ("..###.", ".##...", "##....", "##....", ".##...", "..###.")
CLOUD_ART = ("...###.....", "..#####.##.", ".##########", "###########", ".#########.")
FLAME = ("..#..", ".##..", ".###.", "#####", ".###.")
BULB = (".###.", "#####", "#####", ".###.", ".#.#.")
HOUSE = ("..#..", ".###.", "#####", "#.#.#", "#.#.#")
STARS = [((i * 67 + 11) % WIDTH, 6 + (i * 37) % 100) for i in range(16)]
CONDITION_DE = {
    "sunny": "SONNIG", "clear-night": "KLAR", "partlycloudy": "TEILS BEWOELKT", "cloudy": "BEWOELKT",
    "rainy": "REGEN", "pouring": "STARKREGEN", "snowy": "SCHNEE", "snowy-rainy": "SCHNEEREGEN",
    "fog": "NEBEL", "hail": "HAGEL", "lightning": "GEWITTER", "lightning-rainy": "GEWITTER",
    "windy": "WINDIG", "windy-variant": "WINDIG", "exceptional": "UNWETTER",
}


def ha_entities():
    ids = [HAC.WEATHER, HAC.SUN, HAC.PERSON]
    for _, temp, light in HAC.ROOMS:
        ids += [e for e in (temp, light) if e]
    return ids + [e for _, e in HAC.BATTERIES]


def ha_poll(now):
    """One small non-blocking step of the Home Assistant client per frame."""
    global ha
    if not HA_TOKEN:
        return
    if ha is None:
        if not wlan.isconnected():
            return
        try:
            ha = HAClient(HAC.HOST, HAC.PORT, HA_TOKEN, ha_entities(), gap_ms=800)
        except Exception:
            return
    ha.poll(now)


def ha_state(eid):
    return ha.states.get(eid) if ha and eid else None


def weather():
    """(condition, night) or (None, False) without data."""
    w, sun = ha_state(HAC.WEATHER) if HA_TOKEN else None, ha_state(HAC.SUN) if HA_TOKEN else None
    return (w["state"] if w else None), bool(sun and sun["state"] == "below_horizon")


LEAF_ART = ("....######....", "..##########..", ".############.", "######..######")
UMBRELLA_ART = ("......######......", "...############...", ".################.", "##################")


def outfit():
    """(wear, rain, breath) for the current weather."""
    w = ha_state(HAC.WEATHER) if HA_TOKEN else None
    if not w:
        return "", False, False
    cond, night = weather()
    t = w["attributes"].get("temperature")
    wear = []
    if (t is not None and t < 3) or cond in ("snowy", "snowy-rainy"):
        wear.append("hat")
    if t is not None and t > 26 and not night:
        wear.append("shades")
    rain = cond in ("rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail")
    return "+".join(wear), rain, t is not None and t < 5


def draw_leaf_umbrella(x, y):
    """Big leaf held up by the hamster's right paw (13, 7)."""
    draw_art(LEAF_ART, x + 5 * S, y - 7 * S, S, LEAF_PEN)
    display.set_pen(LEAF_DARK_PEN)
    display.rectangle(x + 13 * S, y - 4 * S, S, 11 * S)


def draw_umbrella(x, y):
    """Red umbrella held up by Clawd's raised left arm (col 1)."""
    draw_art(UMBRELLA_ART, x - CS, y - 10 * CS, CS, UMBRELLA_PEN)
    display.set_pen(UMBRELLA_TIP_PEN)
    display.rectangle(x + 7 * CS, y - 11 * CS, 2 * CS, CS)
    display.set_pen(HANDLE_PEN)
    display.rectangle(x + CS, y - 6 * CS, CS, 8 * CS)


# Sky colour by the sun's elevation (degrees): night, twilight, dusk, day
SKY_STOPS = ((-12, (10, 14, 34)), (-6, (16, 22, 52)), (0, (42, 42, 92)), (6, (55, 72, 132)),
             (15, (62, 100, 168)), (90, (72, 118, 190)))
sky_colours = None  # (sky pen, clock pen, date pen), refreshed every few seconds
sky_checked = -100000


def sky_rgb(elevation):
    for (e0, c0), (e1, c1) in zip(SKY_STOPS, SKY_STOPS[1:]):
        if elevation <= e1:
            u = max(0.0, min(1.0, (elevation - e0) / (e1 - e0)))
            return tuple(int(a + (b - a) * u) for a, b in zip(c0, c1))
    return SKY_STOPS[-1][1]


def update_sky_colours(now):
    """Background, clock and date colours follow the daylight outside."""
    global sky_colours, sky_checked, CLOCK_PEN, DATE_PEN
    if time.ticks_diff(now, sky_checked) < 5000:
        return
    sky_checked = now
    sun = ha_state(HAC.SUN) if HA_TOKEN else None
    if not sun or sun["attributes"].get("elevation") is None:
        return
    r, g, b = sky_rgb(sun["attributes"]["elevation"])
    sky_colours = pen((r, g, b))
    CLOCK_PEN = pen((min(255, r + 42), min(255, g + 52), min(255, b + 70)))
    DATE_PEN = pen((min(255, r + 80), min(255, g + 84), min(255, b + 90)))


def sky_background(now):
    cond, night = weather()
    if cond in ("lightning", "lightning-rainy") and now % 9000 < 110:
        return FLASH_PEN
    update_sky_colours(now)
    return sky_colours


def draw_sky(now):
    """Weather: symbol top left, stars at night, rain, snow, fog."""
    cond, night = weather()
    if not cond:
        return
    if night:
        display.set_pen(STAR_PEN)
        for i, (sx, sy) in enumerate(STARS):
            # each star dims briefly about every 9 s, all at different times
            if (now + i * 1370) % 9000 >= 200:
                display.rectangle(sx, sy, 2, 2)
    # weather symbol in the top left corner, with sun or moon
    draw_weather_icon(cond, night, 9, 3, 3)
    if cond in ("rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail"):
        display.set_pen(RAIN_PEN)
        n = 40 if cond == "pouring" else 24
        for i in range(n):
            ry = int(i * 53 + now * 0.22) % GROUND
            display.rectangle((i * 37 + ry // 8) % WIDTH, ry, 2, 6)
    if cond in ("snowy", "snowy-rainy"):
        display.set_pen(SNOW_PEN)
        for i in range(30):
            fy = int(i * 29 + now * 0.035) % GROUND
            display.rectangle(int(i * 41 + 6 * math.sin(now / 700 + i)) % WIDTH, fy, 3, 3)
    if cond == "fog":
        display.set_pen(FOG_PEN)
        for i in range(4):
            display.rectangle(int(20 * math.sin(now / 2000 + i)) - 20, 40 + i * 30, WIDTH + 40, 8)


def draw_weather_icon(cond, night, x, y, s):
    if night:  # sun or moon always, behind clouds if there are any
        draw_art(MOON_ART, x + s, y, s, MOON_PEN)
    else:
        draw_art(SUN_ART, x, y, s, SUN_PEN)
    if cond not in ("sunny", "clear-night", None):
        dark = cond in ("rainy", "pouring", "lightning", "lightning-rainy", "hail", "snowy-rainy")
        draw_art(CLOUD_ART, x - s, y + 3 * s, s, DARK_CLOUD_PEN if dark else WHEEL_PEN)
    if cond in ("rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail"):
        display.set_pen(RAIN_PEN)
        for i in range(4):
            display.rectangle(x + i * 3 * s, y + 9 * s, s, 2 * s)
    if cond in ("snowy", "snowy-rainy"):
        display.set_pen(SNOW_PEN)
        for i in range(4):
            display.rectangle(x + i * 3 * s + s, y + 9 * s + (i % 2) * s, s, s)
    if cond in ("lightning", "lightning-rainy"):
        draw_art(("..#", ".#.", "###", ".#.", "#.."), x + 4 * s, y + 7 * s, s, ALERT_PEN)


def draw_weather_line():
    """Temperature and condition below the clock."""
    w = ha_state(HAC.WEATHER) if HA_TOKEN else None
    if not w:
        return
    cond, _ = weather()
    t = w["attributes"].get("temperature")
    temp = "%d" % round(t) if t is not None else ""
    desc = CONDITION_DE.get(cond, (cond or "").upper())
    tw = display.measure_text(temp, 2) + 12 if temp else 0
    x, y = (WIDTH - tw - display.measure_text(desc, 1)) // 2, 94
    if temp:
        draw_degrees(temp, x, y, 2, DATE_PEN)
    display.set_pen(DATE_PEN)
    display.text(desc, x + tw, y + 4, -1, 1)


def draw_degrees(text, x, y, scale, colour):
    display.set_pen(colour)
    display.text(text, x, y, -1, scale)
    dx = x + display.measure_text(text, scale) + scale
    display.rectangle(dx, y, 2 * scale, scale)
    display.rectangle(dx, y + 2 * scale, 2 * scale, scale)
    display.rectangle(dx, y, scale, 3 * scale)
    display.rectangle(dx + scale, y, scale, 3 * scale)


GEAR = (".#.#.", "#####", "##.##", "#####", ".#.#.")
SETTING_ROWS = (("leds", "LEDS", "Status: Claude, pipelines"), ("anim_leds", "ANIM LIGHTS", "Moods, party, fight"),
                ("sounds", "SOUNDS", "Pipelines and Claude"), ("anim", "ANIMATION", "Sounds of the scenes"),
                ("music", "MUSIC", "Guybrush and dance songs"))
SETTING_Y0, SETTING_H = 32, 38


def draw_settings(now):
    display.set_pen(BACKGROUND)
    display.clear()
    draw_art(GEAR, 12, 9, 3, DIM_PEN)
    display.set_pen(TEXT_PEN)
    display.text("SETTINGS", 42, 10, -1, 2)
    for i, (key, label, hint) in enumerate(SETTING_ROWS):
        y = SETTING_Y0 + i * SETTING_H
        on = settings[key]
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
    draw_page_dots(4)


def tap_settings(tx, ty):
    i = (ty - SETTING_Y0) // SETTING_H
    if 0 <= i < len(SETTING_ROWS) and ty >= SETTING_Y0:
        key = SETTING_ROWS[i][0]
        settings[key] = not settings[key]
        save_settings()
        if key == "sounds" and settings[key]:
            play("click")


def draw_home(now):
    display.set_pen(BACKGROUND)
    display.clear()
    person = ha_state(HAC.PERSON) if HA_TOKEN else None
    home = person and person["state"] == "home"
    draw_art(HOUSE, 10, 9, 3, TICK_PEN if home else IDLE_PEN)
    display.set_pen(TEXT_PEN)
    display.text("HOME", 42, 10, -1, 2)
    if not HA_TOKEN or not ha or not ha.states:
        display.set_pen(DIM_PEN)
        display.text("Waiting for Home Assistant...", 12, 60, WIDTH - 24, 2)
        draw_page_dots(3)
        return
    if person:
        word = "DA" if home else "UNTERWEGS"
        display.set_pen(TICK_PEN if home else DIM_PEN)
        display.text(word, WIDTH - 12 - display.measure_text(word, 1), 14, -1, 1)

    # weather tile
    cond, night = weather()
    w = ha_state(HAC.WEATHER)
    draw_panel(6, 32, WIDTH - 12, 58)
    draw_weather_icon(cond, night, 18, 41, 4)
    if w:
        a = w["attributes"]
        if a.get("temperature") is not None:
            draw_degrees("%d" % round(a["temperature"]), 82, 42, 4, TEXT_PEN)
        display.set_pen(TEXT_PEN)
        desc = CONDITION_DE.get(cond, (cond or "").upper())
        display.text(desc, WIDTH - 14 - display.measure_text(desc, 1), 44, -1, 1)
        info = []
        if a.get("humidity") is not None:
            info.append("%d%%" % round(a["humidity"]))
        if a.get("wind_speed") is not None:
            info.append("%d km/h" % round(a["wind_speed"]))
        info = "  ".join(info)
        display.set_pen(DIM_PEN)
        display.text(info, WIDTH - 14 - display.measure_text(info, 1), 58, -1, 1)

    # rooms: light bulb, name, temperature and a flame while heating
    y = 96
    for label, temp_id, light_id in HAC.ROOMS:
        light = ha_state(light_id)
        on = light and light["state"] == "on"
        draw_art(BULB, 12, y + 2, 3, ALERT_PEN if on else BULB_OFF_PEN)
        display.set_pen(TEXT_PEN if on else DIM_PEN)
        display.text(label, 34, y + 2, -1, 2)
        st = ha_state(temp_id)
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

    # low batteries, one at a time
    low = []
    for label, eid in HAC.BATTERIES:
        st = ha_state(eid)
        try:
            level = float(st["state"]) if st else 100
        except ValueError:
            continue
        if level < HAC.LOW_BATTERY:
            low.append("%s %d%%" % (label, level))
    if low:
        text = "BATTERIE " + low[(now // 3000) % len(low)]
        display.set_pen(FAIL_PEN if (now // 500) % 2 else DIM_PEN)
        display.text(text[:38], 10, 218, -1, 1)
    draw_page_dots(3)


def draw_agents(now):
    display.set_pen(BACKGROUND)
    display.clear()
    draw_art(MINI_CLAWD, 10, 8, 3, CLAWD_PEN)
    display.set_pen(TEXT_PEN)
    display.text("AGENTS", 42, 10, -1, 2)
    if not agent_list:
        display.set_pen(DIM_PEN)
        display.text("Waiting for Herdr...", 12, 60, WIDTH - 24, 2)
        display.text(wlan.ifconfig()[0] if wlan.isconnected() else "no WiFi yet", 12, 100, -1, 1)
        draw_page_dots(1)
        return
    n = str(len(agent_list))
    display.set_pen(DIM_PEN)
    display.text(n, WIDTH - 12 - display.measure_text(n, 2), 10, -1, 2)
    blink = (now // 400) % 2 == 0
    for i, a in enumerate(agent_list[:5]):
        y = 34 + i * 38
        status = a.get("s", "unknown")
        colour = STATUS_PEN.get(status, DIM_PEN)
        alert = status == "blocked" and blink
        draw_panel(6, y, WIDTH - 12, 36, ALERT_PEN if alert else None)
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
    draw_page_dots(1)


# --- behaviour -------------------------------------------------------------

DURATIONS = {
    "idle": (2000, 4500), "look": (2000, 2000), "walk": (9000, 9000), "eat": (6000, 6000),
    "wash": (2600, 2600), "sleep": (12000, 22000), "happy": (1400, 1400), "startle": (900, 900),
    "sad": (1600, 1600), "ball": (600000, 600000), "event": (600000, 600000),
    "wheel": (600000, 600000), "broken": (600000, 600000), "duo": (600000, 600000),
}
C_DURATIONS = {
    "idle": (2000, 5000), "look": (2000, 3000), "walk": (6000, 6000), "wave": (1800, 1800),
    "think": (3000, 5000), "sleep": (10000, 18000), "happy": (1400, 1400), "sad": (1600, 1600),
    "ball": (600000, 600000), "event": (600000, 600000),
    "work": (600000, 600000), "alert": (600000, 600000), "done": (600000, 600000),
    "duo": (600000, 600000),
}
# Walk and run cycles: (foot lifted, hop in screen pixels)
WALK = ((1, 3), (0, 0), (2, 3), (0, 0))
RUN = ((1, 7), (0, 1), (2, 7), (0, 1))
FREE = ("idle", "look", "walk", "wash", "wave", "think")  # may be pulled into a ball game
STATE_SOUNDS = {"happy": "squeak", "startle": "startle", "eat": "whistle", "sleep": "yawn"}

x = 20
target = x
state = "idle"
t0 = time.ticks_ms()
duration = 3000
last_spawn = 0
eat_sound = 0
last_munch = 0
next_blink = time.ticks_add(t0, 2500)
puff = 0.0

c_x = 140
c_target = c_x
c_state = "idle"
c_t0 = t0
c_duration = 2000
c_last_spawn = 0
c_next_blink = time.ticks_add(t0, 1500)

# Ball game: holder "h" (hamster) or "c" (Clawd), phase "hold" or "fly"
ball = None
scores = [0, 0]
HOLD_MS = 600
FLY_MS = 1100

# Pirate visit: phases enter, scare, flee, laugh, leave, pause, return
ev = None
next_visit = time.ticks_add(t0, random.randint(60000, 180000))
HOME_X, C_HOME_X = 20, 140
WHEEL_CX = HOME_X + 8 * S + 4  # the wheel stands where the hamster lives
shown_pipe = None  # pipeline status the hamster last reacted to
wheel_turn = 0.0
WHEEL_CYCLE_MS = 12000  # every 12 s ...
WHEEL_JOG_MS = 3500     # ... a 3.5 s jog, the rest of the time it rests
cheer_until = 0
BACK_X = 76  # where the hamster backs off to when the pirate walks in

particles = []  # [kind, x, y, vx, vy, life]
was_touched = False
touch_start = touch_last = None
view = "scene"  # or "agents"
name_tag = None  # ("h" or "c", until): name bubble after a tap
frame = 0
FRAME_MS = 25
k = 0.5  # elapsed time in units of 66 ms; per-frame speeds below are tuned for 66 ms
last_now = time.ticks_ms()


def start(name):
    global state, t0, duration, target, last_spawn, eat_sound, last_munch
    state = name
    eat_sound = 0
    last_munch = 0
    t0 = time.ticks_ms()
    last_spawn = -100000
    lo, hi = DURATIONS[name]
    duration = random.randint(lo, hi)
    if name in STATE_SOUNDS:
        play(STATE_SOUNDS[name])
    if name == "walk":
        while abs(target - x) < 12:
            target = random.randint(MIN_X, MAX_X)


def c_start(name):
    global c_state, c_t0, c_duration, c_target, c_last_spawn
    c_state = name
    c_t0 = time.ticks_ms()
    c_last_spawn = -100000
    lo, hi = C_DURATIONS[name]
    c_duration = random.randint(lo, hi)
    if name == "walk":
        while abs(c_target - c_x) < 10:
            c_target = random.randint(C_MIN_X, C_MAX_X)


def start_ball():
    global ball
    ball = {"holder": random.choice("hc"), "phase": "hold", "t0": time.ticks_ms(), "left": random.randint(3, 9)}
    start("ball")
    c_start("ball")


def pick():
    r = random.random()
    if r < 0.10 and c_state in FREE:
        return "ball"
    if r < 0.24 and c_state in FREE:
        return "duo"
    if r < 0.38:
        return "idle"
    if r < 0.52:
        return "look"
    if r < 0.70:
        return "walk"
    if r < 0.82:
        return "eat"
    if r < 0.92:
        return "wash"
    return "sleep"


def c_pick():
    r = random.random()
    if r < 0.06 and state in FREE:
        return "ball"
    if r < 0.16 and state in FREE:
        return "duo"
    if r < 0.38:
        return "idle"
    if r < 0.58:
        return "look"
    if r < 0.74:
        return "walk"
    if r < 0.84:
        return "wave"
    if r < 0.95:
        return "think"
    return "sleep"


def spawn_every(t, ms):
    """True once every ms milliseconds of the hamster's current state."""
    global last_spawn
    if t - last_spawn >= ms:
        last_spawn = t
        return True
    return False


def c_spawn_every(t, ms):
    global c_last_spawn
    if t - c_last_spawn >= ms:
        c_last_spawn = t
        return True
    return False


def hold_point(who):
    if who == "h":
        return x + 8 * S, BASE_Y + 9 * S
    return c_x + CS, C_BASE_Y + CS


def ball_position(now):
    """Ball centre and, while flying, how far along it is (0..1)."""
    bt = time.ticks_diff(now, ball["t0"])
    if ball["phase"] == "hold":
        bx, by = hold_point(ball["holder"])
        return bx, by, None
    u = min(1.0, bt / FLY_MS)
    (fx, fy), (tx, ty), h = ball["src"], ball["dst"], ball["h"]
    return fx + (tx - fx) * u, fy + (ty - fy) * u - 4 * h * u * (1 - u), u


def update_ball(now):
    """Run the ball game. Ends it with a point for whoever didn't drop it."""
    global ball
    bt = time.ticks_diff(now, ball["t0"])
    thrower = ball["holder"]
    catcher = "c" if thrower == "h" else "h"
    if ball["phase"] == "hold" and bt > HOLD_MS:
        miss = ball["left"] <= 0
        tx, ty = hold_point(catcher)
        if miss:  # too high: sails over the catcher and off the screen
            tx += 110 if catcher == "c" else -110
            ty = GROUND - 5
        ball.update(phase="fly", t0=now, src=hold_point(thrower), dst=(tx, ty), h=85 if miss else 55, miss=miss)
        ball["left"] -= 1
        play("toss")
    elif ball["phase"] == "fly" and bt > FLY_MS:
        if ball["miss"]:
            ball = None
            scores[0 if thrower == "h" else 1] += 1
            if thrower == "h":
                start("happy")
                c_start("sad")
            else:
                start("sad")
                c_start("happy")
        else:
            ball.update(holder=catcher, phase="hold", t0=now)
            play("catch")


# --- scenes for two ----------------------------------------------------------
# Hamster and Clawd do something together. update_duo() runs the choreography:
# it moves both, and returns how each one looks this frame plus extra effects.

DUO_KINDS = (("fight", 3), ("chase", 3), ("dance", 2), ("snack", 2), ("leap", 2))
MEET_X, C_MEET_X = 74, 128  # standing nose to nose
duo = None


def start_duo(kind=None):
    global duo
    if kind is None:
        r = random.uniform(0, sum(w for _, w in DUO_KINDS))
        for kind, w in DUO_KINDS:
            r -= w
            if r <= 0:
                break
    duo = {"kind": kind, "phase": "start", "t0": time.ticks_ms(), "spawn": -100000}
    start("duo")
    c_start("duo")


def walk_to(pos, target, speed):
    """Move pos towards target by speed px per 66 ms; returns (pos, arrived)."""
    step_px = speed * k
    if abs(target - pos) <= step_px:
        return target, True
    return pos + (step_px if target > pos else -step_px), False


def arc(u, height):
    return int(height * math.sin(math.pi * max(0.0, min(1.0, u))))


def update_duo(now):
    global duo, x, c_x
    d = duo
    t = time.ticks_diff(now, d["t0"])
    ph, kind = d["phase"], d["kind"]
    H = {"eyes": "open", "look": 1}
    C = {"eyes": "open", "look": -1}
    fx = []

    def go(phase):
        d["phase"] = phase
        d["t0"] = now
        d["spawn"] = -100000

    def every(ms):
        if t - d["spawn"] >= ms:
            d["spawn"] = t
            return True
        return False

    def walking(who, ms=110):
        (H if who == "h" else C)["step"], (H if who == "h" else C)["jump"] = WALK[(t // ms) % 4]

    def running(who):
        (H if who == "h" else C)["step"], (H if who == "h" else C)["jump"] = RUN[(t // 70) % 4]

    def meet(next_phase, speed=2.5):
        global x, c_x
        x, a = walk_to(x, MEET_X, speed)
        c_x, b = walk_to(c_x, C_MEET_X, speed)
        if not a:
            walking("h")
        if not b:
            walking("c", 120)
        if a and b:
            go(next_phase)

    if ph == "home":  # everyone back to their spot, then the scene ends
        x, a = walk_to(x, HOME_X, 2.5)
        c_x, b = walk_to(c_x, C_HOME_X, 2.0)
        H["look"] = -1 if x > HOME_X else 0
        C["look"] = 1 if c_x < C_HOME_X else -1
        if not a:
            walking("h")
        if not b:
            walking("c", 120)
        if a and b:
            duo = None
            start("idle")
            c_start("idle")
        return H, C, fx

    if kind == "fight":
        if ph == "start":
            meet("argue")
        elif ph == "argue":  # angry faces, taking turns to puff up
            H["eyes"] = C["eyes"] = "angry"
            beat = (t // 300) % 2
            H["jump"] = 5 if beat == 0 else 0
            C["jump"] = 5 if beat == 1 else 0
            C["arms"] = (beat == 1, False)
            if every(350):
                play("grr", 0.08)
                who = (t // 350) % 2
                px = x + 12 * S if who == 0 else c_x + 10 * CS
                particles.append(["anger", px, (BASE_Y if who == 0 else C_BASE_Y) - 14, 0, -0.4, 14])
            if t > 2200:
                go("brawl")
        elif ph == "brawl":  # a cloud of dust with flying fists
            H["hide"] = C["hide"] = True
            fx.append(("cloud", (x + 8 * S + c_x + 8 * CS) // 2))
            if every(260):
                play(("pow", "bam", "pow", "bonk")[(t // 260) % 4])
                particles.append(["spark", (x + c_x) // 2 + 40 + random.randint(-50, 50), GROUND - 60 + random.randint(-30, 20),
                                  random.uniform(-2, 2), random.uniform(-2.5, -0.5), 12])
            if t > 2400:
                go("apart")
        elif ph == "apart":  # thrown apart
            if every(10000):
                play("whoosh")
            x, _ = walk_to(x, 24, 9)
            c_x, _ = walk_to(c_x, C_HOME_X + 10, 9)
            H["eyes"] = C["eyes"] = "wide"
            H["jump"], C["jump"] = arc(t / 600, 22), arc(t / 600, 18)
            if t > 650:
                go("dizzy")
        elif ph == "dizzy":  # stars circling their heads
            H["eyes"] = "closed" if (t // 300) % 2 else "wide"
            C["eyes"] = "closed" if (t // 300) % 2 == 0 else "open"
            H["look"] = C["look"] = 0
            H["bob"] = (t // 250) % 2
            fx.append(("stars", x + 8 * S, BASE_Y - 4))
            fx.append(("stars", c_x + 8 * CS, C_BASE_Y - 6))
            if t > 1800:
                go("sulk")
        elif ph == "sulk":  # turned away from each other
            H["look"], C["look"] = -1, 1
            H["bob"], C["eyes"] = 1, "sad"
            if t > 1600:
                go("makeup")
        elif ph == "makeup":  # Clawd comes over first, the hamster turns round
            c_x, b = walk_to(c_x, C_MEET_X, 1.4)
            if not b:
                walking("c", 160)
            if t > 900:
                x, a = walk_to(x, MEET_X, 1.6)
                if not a:
                    walking("h", 150)
            else:
                H["look"], H["bob"] = -1, 1
                a = False
            if a and b:
                go("hug")
        elif ph == "hug":
            H["eyes"] = C["eyes"] = "happy"
            H["blush"] = True
            H["paws"] = ((13, 8), (14, 7))
            C["arms"] = (3, False)
            H["bob"] = C["bob"] = (t // 500) % 2
            if t < 100 and every(10000):
                play("aww")
            if every(320):
                particles.append(["heart", x + 14 * S + random.randint(-8, 8), BASE_Y - 4, random.uniform(-0.4, 0.4), -1.4, 24])
            if t > 2400:
                go("home")

    elif kind == "chase":
        if ph == "start":  # Clawd sneaks up
            c_x, b = walk_to(c_x, x + 70, 1.0)
            C["eyes"] = "down"
            walking("c", 200)
            H["look"], H["sniff"] = 0, (t // 75) % 2 == 0
            if b:
                go("spot")
        elif ph == "spot":
            H["eyes"] = C["eyes"] = "wide"
            H["jump"] = arc(t / 400, 16)
            fx.append(("alert", x + 6 * S, BASE_Y - H["jump"] - 30))
            if t > 700:
                go("flee")
        elif ph == "flee":  # off to the left...
            H["look"] = C["look"] = -1
            H["eyes"] = "wide"
            x, a = walk_to(x, -80, 7)
            running("h")
            if t > 250:
                c_x, b = walk_to(c_x, -100, 6.2)
                running("c")
            else:
                b = False
            if a and b:
                x, c_x = WIDTH + 10, WIDTH + 110  # ...and back in from the right
                go("back")
        elif ph == "back":
            H["look"] = C["look"] = -1
            x, a = walk_to(x, HOME_X, 6)
            c_x, b = walk_to(c_x, C_HOME_X, 5.6)
            if not a:
                running("h")
            if not b:
                running("c")
            if a and b:
                go("pant")
        elif ph == "pant":
            H["eyes"] = C["eyes"] = "closed"
            H["mouth"] = 1 + (t // 150) % 2
            H["bob"] = C["bob"] = (t // 160) % 2
            H["look"] = C["look"] = 0
            if t > 1500:
                go("meet")
        elif ph == "meet":
            H["eyes"] = C["eyes"] = "happy"
            meet("highfive")
        elif ph == "highfive":
            H["eyes"] = C["eyes"] = "happy"
            H["jump"], C["jump"] = arc(t / 700, 18), arc(t / 700, 16)
            H["paws"] = ((14, 6), (14, 5))
            C["arms"] = (True, False)
            if 330 < t < 400 and every(500):
                for _ in range(6):
                    particles.append(["spark", x + 15 * S, BASE_Y - 10, random.uniform(-2, 2), random.uniform(-2.5, 0), 14])
            if t > 1200:
                go("home")

    elif kind == "dance":
        if ph == "start":
            # with music on and dance.rtttl on the Presto: dance to it, in time
            tune, beat_ms = load_rtttl("dance.rtttl") if settings["music"] else (None, None)
            if tune:
                play_music(tune)
                d["beat"] = beat_ms
                d["len"] = min(25000, sum(ms for _, ms in tune))
            go("groove")
        elif ph == "groove":
            bm = d.get("beat", 420)
            beat = t // bm
            on = beat % 2 == 0
            H["eyes"] = C["eyes"] = "happy"
            H["look"] = C["look"] = 1 if (beat // 2) % 2 else -1
            H["jump"] = 9 if on and t % bm < bm * 6 // 10 else 0
            C["jump"] = 9 if not on and t % bm < bm * 6 // 10 else 0
            H["bob"] = 1 if on and t % bm >= bm * 7 // 10 else 0
            H["paws"] = ((3, 8), (12, 7)) if on else ((3, 7), (12, 8))
            C["arms"] = (on, not on)
            if every(bm):
                particles.append(["note", random.choice((x + 8 * S, c_x + 8 * CS)) + random.randint(-20, 20),
                                  GROUND - 80, random.uniform(-0.6, 0.6), -1.0, 30])
            if t > d.get("len", 6500):
                go("finale")
        elif ph == "finale":
            H["eyes"] = C["eyes"] = "happy"
            H["jump"], C["jump"] = arc(t / 700, 24), arc(t / 700, 22)
            H["paws"] = ((3, 6), (12, 6))
            C["arms"] = (True, True)
            if every(150):
                particles.append(["spark", random.randint(30, WIDTH - 30), GROUND - 90, random.uniform(-1, 1), -1.5, 16])
            if t > 1300:
                go("home")

    elif kind == "snack":
        sx = (x + 8 * S + c_x + 8 * CS) // 2 if ph == "start" else d.get("sx", 110)
        if ph == "start":  # a seed drops between them
            d["sx"] = sx
            H["eyes"] = C["eyes"] = "wide"
            fx.append(("seed", sx - S, -20 + (GROUND - 12 + 20) * min(1.0, (t / 900) ** 2)))
            if t > 900:
                go("rush")
        elif ph == "rush":  # the hamster is faster
            fx.append(("seed", sx - S, GROUND - 12))
            x, a = walk_to(x, sx - 8 * S, 5)
            c_x, _ = walk_to(c_x, sx + 4, 2.4)
            if not a:
                running("h")
            walking("c", 120)
            if a:
                go("grab")
        elif ph == "grab":
            H["seed"], H["paws"] = True, ((6, 10), (9, 10))
            H["mouth"] = 1 + (t // 150) % 2
            H["look"] = 0
            C["eyes"] = "sad"
            if t > 1400:
                go("share")
        elif ph == "share":  # half for Clawd
            H["eyes"], H["look"] = "happy", 1
            u = min(1.0, t / 700)
            hx, hy = x + 8 * S, BASE_Y + 9 * S
            cx, cy = c_x + 2 * CS, C_BASE_Y + CS
            fx.append(("seed", int(hx + (cx - hx) * u), int(hy + (cy - hy) * u) - arc(u, 30)))
            C["eyes"] = "wide" if u > 0.5 else "sad"
            if t > 800:
                go("munch")
        elif ph == "munch":
            H["eyes"] = C["eyes"] = "happy"
            H["mouth"] = 1 + (t // 150) % 2
            H["puff"] = 1
            C["bob"] = (t // 160) % 2
            C["arms"] = (3 + (t // 160) % 2, False)
            if every(400):
                particles.append(["heart", (x + c_x) // 2 + 40, BASE_Y, random.uniform(-0.5, 0.5), -1.4, 24])
            if t > 2200:
                go("home")

    elif kind == "leap":
        if ph == "start":  # make room
            x, a = walk_to(x, 4, 3)
            c_x, b = walk_to(c_x, 88, 2.2)
            H["look"] = -1 if not a else 1
            if not a:
                walking("h")
            if not b:
                walking("c", 120)
            if a and b:
                go("leap1")
                d["from"] = x
        elif ph in ("leap1", "leap2"):
            u = min(1.0, t / 800)
            dest = c_x + 84 if ph == "leap1" else 4
            x = int(d["from"] + (dest - d["from"]) * u)
            H["jump"] = arc(u, 62)
            H["look"] = 1 if ph == "leap1" else -1
            H["paws"] = ((3, 7), (12, 7))
            C["eyes"] = "wide"
            C["look"] = -1 if u < 0.5 else 1
            if ph == "leap2":
                C["look"] = -C["look"]
            if u >= 1.0:
                go("land" if ph == "leap1" else "clap")
        elif ph == "land":
            H["bob"] = 1 if t < 150 else 0
            H["eyes"], H["look"] = "happy", -1
            C["eyes"], C["look"] = "wide", 1
            if t > 1100:
                d["from"] = x
                go("leap2")
        elif ph == "clap":  # applause
            H["eyes"] = C["eyes"] = "happy"
            C["arms"] = (3 + (t // 120) % 2, 3 + (t // 120) % 2)
            H["bob"] = (t // 300) % 2
            if every(200):
                particles.append(["spark", c_x + random.randint(0, 16) * CS, C_BASE_Y - 10, random.uniform(-1, 1), -1.5, 14])
            if t > 1400:
                go("home")
    return H, C, fx


def draw_duo_fx(fx, now):
    for f in fx:
        if f[0] == "cloud":  # grey dust blob that boils, limbs poking out
            cx, cy = f[1], GROUND - 40
            seed = now // 90
            for i in range(16):
                a = i * 0.39 + (seed % 7) * 0.2
                r = 18 + ((seed * 7 + i * 13) % 14)
                display.set_pen(WHEEL_PEN if i % 3 else STAND_PEN)
                display.rectangle(cx + int(r * math.cos(a)) - 10, cy + int(r * 0.7 * math.sin(a)) - 10, 20, 20)
            display.set_pen(WHEEL_PEN)
            display.rectangle(cx - 26, cy - 18, 52, 36)
            for i in range(3):  # fists and feet
                a = (seed * 1.7 + i * 2.1) % 6.28
                display.set_pen(COLOURS["#"] if i % 2 else CLAWD_PEN)
                display.rectangle(cx + int(42 * math.cos(a)) - 5, cy + int(30 * math.sin(a)) - 5, 10, 10)
            word = ("POW!", "BAM!", "BONK!")[(now // 600) % 3]
            display.set_pen(ALERT_PEN)
            display.text(word, cx - display.measure_text(word, 2) // 2 + ((now // 600) % 2) * 20 - 10, cy - 58, -1, 2)
        elif f[0] == "stars":
            hx, hy = f[1], f[2]
            display.set_pen(ALERT_PEN)
            for i in range(3):
                a = now / 160 + i * 2.09
                display.rectangle(hx + int(16 * math.cos(a)) - 2, hy + int(5 * math.sin(a)) - 2, 4, 4)
        elif f[0] == "seed":
            draw_art(("##", "#.", "##"), f[1], f[2], S, COLOURS["e"])
        elif f[0] == "alert":
            bx0, by0 = int(f[1]), int(f[2])
            display.set_pen(ALERT_PEN)
            display.rectangle(bx0, by0, 18, 22)
            display.set_pen(EYE_PEN)
            display.rectangle(bx0 + 7, by0 + 4, 4, 9)
            display.rectangle(bx0 + 7, by0 + 15, 4, 3)


def update_event(now):
    global ev, x, c_x, next_visit
    et = time.ticks_diff(now, ev["t0"])
    ph = ev["phase"]

    def go(phase):
        ev["phase"] = phase
        ev["t0"] = now

    if ph == "enter":  # he walks in, the two nervously back away to the right
        ev["gx"] += 2.5 * k
        x = min(BACK_X, x + 2 * k)
        c_x = min(C_MAX_X, c_x + 1.2 * k)
        if ev["gx"] >= 4:
            go("scare")
    elif ph == "scare" and et > 1300:
        go("flee")
    elif ph == "flee":
        x += 8 * k
        c_x += 7 * k
        if x > WIDTH + 10 and c_x > WIDTH + 10:
            go("laugh")
    elif ph == "laugh" and et > 1800:
        go("leave")
    elif ph == "leave":
        ev["gx"] -= 2.5 * k
        if ev["gx"] < -GB_W * GB - 4:
            go("pause")
    elif ph == "pause" and et > 2000:
        go("return")
    elif ph == "return":
        x = max(HOME_X, x - 2.5 * k)
        c_x = max(C_HOME_X, c_x - 2.5 * k)
        if x == HOME_X and c_x == C_HOME_X:
            ev = None
            next_visit = time.ticks_add(now, random.randint(120000, 300000))
            start("idle")
            c_start("idle")


while True:
    now = time.ticks_ms()
    k = min(3.0, time.ticks_diff(now, last_now) / 66)
    last_now = now

    # Touch: a swipe switches between the scene and the agent list, a tap
    # (on release) pokes the hamster or Clawd
    touch.poll()
    tapped = None
    if touch.state:
        touch_last = (touch.x, touch.y)
        if not was_touched:
            touch_start = touch_last
    elif was_touched and touch_start:
        dx = touch_last[0] - touch_start[0]
        if abs(dx) > 40:
            view = VIEWS[(VIEWS.index(view) + (1 if dx < 0 else -1)) % len(VIEWS)]
            if view != "scene":
                stop_music()
        elif view == "scene":
            tapped = touch_start
        elif view == "settings":
            tap_settings(*touch_start)
    was_touched = touch.state
    if tapped and not ball and not ev and not duo:
        name_tag = ("h" if tapped[0] < WIDTH // 2 else "c", time.ticks_add(now, 1800))
        if tapped[0] < WIDTH // 2:
            if state == "sleep":
                start("startle")
            elif state not in ("happy", "startle"):
                start("happy")
                if c_state in FREE:
                    c_start("wave")
        elif c_state not in ("happy",):
            c_start("happy")

    if ball:
        update_ball(now)
    elif ev is None and not duo and state not in ("wheel", "broken") and time.ticks_diff(now, next_visit) > 0:
        ev = {"phase": "enter", "t0": now, "gx": -GB_W * GB - 4}
        play_music(guybrush_tune())
        start("event")
        c_start("event")
    if ev:
        update_event(now)
    t = time.ticks_diff(now, t0)
    if t > duration:
        nxt = pick()
        if nxt == "ball":
            start_ball()
        elif nxt == "duo":
            start_duo()
        else:
            start(nxt)
        t = 0
    ct = time.ticks_diff(now, c_t0)
    if ct > c_duration:
        nxt = c_pick()
        if nxt == "ball":
            start_ball()
        elif nxt == "duo":
            start_duo()
        else:
            c_start(nxt)
        ct = 0

    # GitLab pipeline status takes over the hamster (after a game or the pirate)
    if pipe_status != shown_pipe and state not in ("ball", "event", "duo"):
        if shown_pipe == "running" and pipe_status == "success":
            start("happy")  # all green: cheer
            cheer_until = time.ticks_add(now, 4000)
        elif shown_pipe == "running" and pipe_status == "failed":
            start("startle")
        shown_pipe = pipe_status
    if pipe_beep:  # set by watch_pipes, per pipeline
        play(pipe_beep)
        pipe_beep = None
    wanted_h = {"running": "wheel", "failed": "broken"}.get(pipe_status)
    if state not in ("ball", "event", "duo", "happy", "startle"):
        if wanted_h and state != wanted_h:
            x = target = WHEEL_CX - 8 * S
            start(wanted_h)
        elif not wanted_h and state in ("wheel", "broken"):
            start("idle")

    # Herdr agent status takes over Clawd (but never interrupts a game, the
    # pirate or a tap)
    if frame % 4 == 0:
        poll_agent(now)
        sync_clock(now)
    ha_poll(now)
    if agent_beep:  # set by watch_agents on real changes only
        play("agent_alert" if agent_beep == "alert" else "agent_done")
        agent_beep = None
    wanted = CLAWD_FOR.get(agent_status)
    if wanted == "alert" and (ball or duo):  # a question for you beats playing
        ball = duo = None
        start("idle")
        c_start("idle")
    if c_state not in ("ball", "event", "duo", "happy"):
        if wanted and c_state != wanted:
            c_start(wanted)
        elif not wanted and c_state in ("work", "alert", "done"):
            c_start("idle")
    t = time.ticks_diff(now, t0)
    ct = time.ticks_diff(now, c_t0)
    bx = by = bu = None
    if ball:
        bx, by, bu = ball_position(now)
    duo_h = duo_c = None
    duo_fx = ()
    if duo:
        duo_h, duo_c, duo_fx = update_duo(now)
        t = time.ticks_diff(now, t0)
        ct = time.ticks_diff(now, c_t0)

    # --- hamster ---
    eyes, look, step, bob, jump = "open", 0, 0, 0, 0
    paws, mouth, blush, seed, ear, sniff = (), 0, False, False, False, False
    seed_y = None

    if state == "idle":
        bob = (t // 1100) % 2
        sniff = t % 2600 < 300 and (t // 75) % 2 == 0
        ear = t % 3700 < 160
    elif state == "look":
        look = (-1, 0, 1, 0)[(t // 500) % 4]
    elif state == "walk":
        if x != target:
            d = 1 if target > x else -1
            look = d
            x += d * 2.5 * k
            if (d > 0 and x >= target) or (d < 0 and x <= target):
                x = target
                duration = t + 500  # stand still for a moment, then pick something new
            step, jump = WALK[(t // 110) % 4]
        else:
            sniff = (t // 75) % 2 == 0
    elif state == "eat":
        if t < 900:  # a seed drops from above
            eyes = "wide"
            seed_y = -30 + (BASE_Y + 9 * S + 30) * (t / 900) ** 2
        elif t < 5000:  # munch munch, cheeks fill up
            seed = t < 4200
            if eat_sound == 0:
                play("catch")
                eat_sound = 1
            elif seed and t - last_munch >= 300:
                play("munch", 0.15)
                last_munch = t
            paws = ((6, 10), (9, 10))
            mouth = 1 + (t // 150) % 2
            eyes = "closed" if (t // 900) % 3 == 2 else "open"
            puff = max(puff, min(2.0, (t - 900) / 1500))
            if seed and spawn_every(t, 350):
                particles.append(["crumb", x + 8 * S, BASE_Y + 10 * S, random.uniform(-1.5, 1.5), -1.0, 25])
        else:
            eyes = "happy"
            blush = True
            if eat_sound == 1:
                play("yum")
                eat_sound = 2
    elif state == "wash":
        eyes = "closed"
        up = (t // 250) % 2
        paws = ((3, 7 + up), (12, 8 - up))
    elif state == "sleep":
        eyes = "closed"
        bob = (t // 1500) % 2
        if spawn_every(t, 1300):
            if t > 2000:
                play("snore", 0.03)
            particles.append(["zed", x + 13 * S, BASE_Y + S, 0.4, -0.7, 45])
    elif state == "happy":
        eyes = "happy"
        blush = True
        phase = (t % 700) / 700
        if phase < 0.12 or phase > 0.9:
            bob = 1  # squash on the ground between hops
        else:
            jump = int(28 * math.sin(math.pi * (phase - 0.12) / 0.78))
        if spawn_every(t, 350):
            particles.append(["heart", x + random.randint(0, 12) * S, BASE_Y, random.uniform(-0.5, 0.5), -1.6, 22])
    elif state == "startle":
        eyes = "wide"
        jump = int(18 * math.sin(math.pi * min(1, t / 400)))
        if 400 < t < 520:
            bob = 1
    elif state == "sad":
        eyes = "closed"
        bob = 1
    elif state == "wheel":  # pipeline running: a calm jog now and then, mostly resting
        if t % WHEEL_CYCLE_MS < WHEEL_JOG_MS:
            look = 1
            step, jump = WALK[(t // 140) % 4]
            jump = jump // 2
            wheel_turn += 0.035 * k
        else:
            bob = (t // 1300) % 2
            sniff = t % 2600 < 300 and (t // 75) % 2 == 0
            look = (0, 0, 1, 0, -1)[(t // 1700) % 5]
    elif state == "broken":  # pipeline failed: sits in the stopped wheel
        eyes = "closed" if (t // 2500) % 3 else "open"
        look = 0
        bob = 1
        if spawn_every(t, 900):  # smoke from the hub
            particles.append(["smoke", WHEEL_CX - 4 + random.randint(-6, 6), WHEEL_CY - 6, random.uniform(-0.3, 0.3), -0.8, 30])
    elif state == "ball" and ball:
        cx = x + 8 * S
        look = 1 if bx > cx + 8 else (-1 if bx < cx - 8 else 0)
        if ball["phase"] == "hold" and ball["holder"] == "h":
            paws = ((6, 10), (9, 10))
            bob = 1 if time.ticks_diff(now, ball["t0"]) > HOLD_MS - 200 else 0  # wind up
        elif bu is not None and ball["holder"] == "c":  # incoming
            paws = ((3, 8), (12, 8))
            if bu > 0.5:
                eyes = "wide"
        elif bu is not None and bu < 0.25:
            jump = 6  # just threw it

    elif state == "duo" and duo_h:
        eyes, look = duo_h["eyes"], duo_h["look"]
        step, jump, bob = duo_h.get("step", 0), duo_h.get("jump", 0), duo_h.get("bob", 0)
        paws, mouth, blush = duo_h.get("paws", ()), duo_h.get("mouth", 0), duo_h.get("blush", False)
        seed, sniff = duo_h.get("seed", False), duo_h.get("sniff", False)
        if duo_h.get("puff"):
            puff = max(puff, 1.0)
    elif state == "event" and ev:
        ph, et = ev["phase"], time.ticks_diff(now, ev["t0"])
        if ph == "enter":
            look = -1
            if ev["gx"] > -40:
                eyes = "wide"
            if x < BACK_X:
                step, jump = WALK[(t // 110) % 4]
        elif ph == "scare":
            eyes = "wide"
            paws = ((3, 8), (12, 8))
            jump = int(20 * math.sin(math.pi * min(1, et / 400)))
        elif ph in ("flee", "return"):
            eyes = "wide" if ph == "flee" else "open"
            look = 1 if ph == "flee" else -1
            if ph == "flee":
                step, jump = RUN[(et // 70) % 4]
            elif x > HOME_X:
                step, jump = WALK[(et // 110) % 4]

    # Blink now and then while awake
    if eyes == "open" and time.ticks_diff(now, next_blink) > 0:
        eyes = "closed"
        if time.ticks_diff(now, next_blink) > 140:
            next_blink = time.ticks_add(now, random.randint(1800, 5000))

    # Stuffed cheeks slowly go back to normal
    if state != "eat":
        puff = max(0.0, puff - 0.012 * k)

    # --- Clawd ---
    c_eyes, c_look, c_bob, c_step, c_jump = "open", 0, 0, 0, 0
    c_arms = (False, False)
    think_dots = 0
    laptop = False
    bubble = None

    if c_state == "idle":
        c_bob = (ct // 900) % 2
    elif c_state == "look":
        c_look = (-1, -1, 0, 1)[(ct // 600) % 4]  # mostly at the hamster
    elif c_state == "walk":
        if c_x != c_target:
            d = 1 if c_target > c_x else -1
            c_look = d
            c_x += d * 1.6 * k
            if (d > 0 and c_x >= c_target) or (d < 0 and c_x <= c_target):
                c_x = c_target
                c_duration = ct + 500
            c_step, c_jump = WALK[(ct // 120) % 4]
    elif c_state == "wave":
        c_eyes = "happy"
        c_look = -1
        c_arms = ((ct // 250) % 2 == 0, False)
    elif c_state == "think":
        c_look = 1
        think_dots = 1 + (ct // 400) % 4
    elif c_state == "sleep":
        c_eyes = "closed"
        c_bob = (ct // 1600) % 2
        if c_spawn_every(ct, 1500):
            particles.append(["zed", c_x + 13 * CS, C_BASE_Y - 6, 0.4, -0.7, 45])
    elif c_state == "happy":
        c_eyes = "happy"
        c_arms = (True, True)
        phase = (ct % 700) / 700
        if phase < 0.12 or phase > 0.9:
            c_bob = 1
        else:
            c_jump = int(24 * math.sin(math.pi * (phase - 0.12) / 0.78))
        if c_spawn_every(ct, 300):
            particles.append(["spark", c_x + random.randint(0, 14) * CS, C_BASE_Y, random.uniform(-0.6, 0.6), -1.6, 20])
    elif c_state == "sad":
        c_eyes = "sad"
        c_bob = 1
    elif c_state == "work":  # typing away on a laptop
        laptop = True
        c_eyes = "down"
        tap = (ct // 110) % 4
        c_arms = (5 if tap == 0 else 4, 5 if tap == 2 else 4)
        c_bob = 1 if (ct // 2200) % 4 == 3 else 0
        if (ct // 2600) % 3 == 2:
            c_eyes, c_look = "open", 1  # glance up and think
            think_dots = 1 + (ct // 400) % 4
    elif c_state == "alert":  # waiting for an answer: wave and jump
        c_eyes = "wide" if (ct // 1200) % 2 else "open"
        c_look = -1
        c_arms = ((ct // 180) % 2 == 0, False)
        c_jump = int(6 * abs(math.sin(ct * math.pi / 500)))
        bubble = "!"
    elif c_state == "done":
        c_eyes = "happy"
        if ct < 1400:  # two hops, then stand proud
            phase = (ct % 700) / 700
            c_jump = int(20 * math.sin(math.pi * phase))
            c_arms = (True, True)
        else:
            c_bob = (ct // 1000) % 2
        bubble = "tick"
    elif c_state == "ball" and ball:
        ccx = c_x + 8 * CS
        c_look = 1 if bx > ccx + 8 else (-1 if bx < ccx - 8 else 0)
        if ball["phase"] == "hold" and ball["holder"] == "c":
            c_arms = (True, False)
        elif bu is not None and ball["holder"] == "h":  # incoming
            c_arms = (True, False)
            if bu > 0.5:
                c_eyes = "wide"
        elif bu is not None and bu < 0.25:
            c_jump = 5

    elif c_state == "duo" and duo_c:
        c_eyes, c_look = duo_c["eyes"], duo_c["look"]
        c_step, c_jump, c_bob = duo_c.get("step", 0), duo_c.get("jump", 0), duo_c.get("bob", 0)
        c_arms = duo_c.get("arms", (False, False))
    elif c_state == "event" and ev:
        ph, et = ev["phase"], time.ticks_diff(now, ev["t0"])
        if ph == "enter":
            c_look = -1
            if ev["gx"] > -40:
                c_eyes = "wide"
            if c_x < C_MAX_X:
                c_step, c_jump = WALK[(ct // 120) % 4]
        elif ph == "scare":
            c_eyes = "wide"
            c_arms = (True, True)
            c_jump = int(16 * math.sin(math.pi * min(1, max(0, et - 100) / 400)))
        elif ph in ("flee", "return"):
            c_eyes = "wide" if ph == "flee" else "open"
            c_look = 1 if ph == "flee" else -1
            if ph == "flee":
                c_step, c_jump = RUN[(et // 70) % 4]
            elif c_x > C_HOME_X:
                c_step, c_jump = WALK[(et // 120) % 4]

    if c_eyes == "open" and time.ticks_diff(now, c_next_blink) > 0:
        c_eyes = "closed"
        if time.ticks_diff(now, c_next_blink) > 140:
            c_next_blink = time.ticks_add(now, random.randint(2000, 6000))

    # --- dress for the weather ---
    wear, rain, breath = outfit() if HA_TOKEN else ("", False, False)
    h_umbrella = rain and state in ("idle", "look", "walk", "sleep", "sad", "startle")
    c_umbrella = rain and c_state in ("idle", "look", "walk", "think", "wave", "sleep", "sad", "done")
    if h_umbrella:
        paws = ((13, 7),)
    if c_umbrella:
        c_arms = (True, c_arms[1] if c_state == "wave" else False)
    if breath and view == "scene" and frame % 75 == 0 and state not in ("event", "duo"):
        particles.append(["breath", x + 9 * S, BASE_Y + 7 * S - jump, 0.8, -0.3, 18])
    if breath and view == "scene" and frame % 75 == 37 and c_state not in ("event", "duo", "work"):
        particles.append(["breath", c_x + 15 * CS, C_BASE_Y + 3 * CS - c_jump, 0.7, -0.3, 18])

    # --- draw ---
    sky_pen = sky_background(now)
    if view == "agents":
        draw_agents(now)
    elif view == "home":
        draw_home(now)
    elif view == "settings":
        draw_settings(now)
    elif view == "pipelines":
        draw_pipelines(now)
    else:
        draw_scene(((x + 8 * S, 12 * S - jump), (c_x + 8 * CS, 14 * CS - c_jump)))
        draw_sky(now)
        draw_clock(now)
        draw_weather_line()
        in_wheel = state in ("wheel", "broken")
        if in_wheel:
            draw_wheel_back(WHEEL_CX, -wheel_turn if state == "wheel" else 0.3)
            jump += WHEEL_LIFT
        if not (duo_h and duo_h.get("hide")):
            draw_hamster(x, BASE_Y - jump, eyes, look, step, bob, int(puff + 0.5), paws, mouth, blush, seed, ear, sniff,
                         wear)
            if h_umbrella:
                draw_leaf_umbrella(x, BASE_Y - jump + bob * S)
        if in_wheel:
            draw_wheel_rim(WHEEL_CX, -int(wheel_turn * 6) if state == "wheel" else 0, state == "broken")
            if state == "broken" and (t // 500) % 2 == 0:
                draw_art(CROSS, WHEEL_CX - 8, WHEEL_CY - WHEEL_R - 24, 3, FAIL_PEN)
        if time.ticks_diff(cheer_until, now) > 0:
            draw_art(TICK, x + 5 * S, BASE_Y - jump - 22, 4, TICK_PEN)
        if not (duo_c and duo_c.get("hide")):
            draw_clawd(c_x, C_BASE_Y - c_jump, c_eyes, c_look, c_bob, c_step, c_arms, laptop, wear)
            if c_umbrella:
                draw_umbrella(c_x, C_BASE_Y - c_jump + c_bob * CS)
        draw_duo_fx(duo_fx, now)
        if name_tag and time.ticks_diff(name_tag[1], now) > 0:  # who's who
            if name_tag[0] == "h":
                draw_bubble("MESSY", int(x) + 2, BASE_Y - jump - 30)
            else:
                draw_bubble("CLAWD", int(c_x) + 6, C_BASE_Y - c_jump - 30)
        if bubble == "!":
            bx0, by0 = int(c_x) + 6 * CS, C_BASE_Y - c_jump - 30
            display.set_pen(ALERT_PEN)
            display.rectangle(bx0, by0, 18, 22)
            display.rectangle(bx0 + 4, by0 + 22, 4, 4)
            display.set_pen(EYE_PEN)
            display.rectangle(bx0 + 7, by0 + 4, 4, 9)
            display.rectangle(bx0 + 7, by0 + 15, 4, 3)
        elif bubble == "tick":
            draw_art(TICK, int(c_x) + 5 * CS, C_BASE_Y - c_jump - 22, 4, TICK_PEN)
        if laptop:  # Claude Code style spinner star
            draw_art(SPARK if (ct // 150) % 2 else SPARK_X, int(c_x) + 14 * CS, C_BASE_Y - 12, 3, CLAWD_PEN)
        if ev and ev["phase"] in ("enter", "scare", "flee", "laugh", "leave"):
            ph, et = ev["phase"], time.ticks_diff(now, ev["t0"])
            legs, arms, gbob = "stand", "down", 0
            if ph in ("enter", "leave"):
                legs, arms, gbob = GB_WALK[(et // 130) % 4]
            elif ph == "scare":
                arms = "up"
                gbob = -3 if et < 150 else 0
            elif ph == "laugh":
                gbob = -2 if (et // 200) % 2 == 0 else 0  # shoulders shake
            draw_guybrush(ev["gx"], flip=ph == "leave", legs=legs, arms=arms,
                          mouth=ph == "scare" or (ph == "laugh" and (et // 200) % 2 == 0), bob=gbob)
            if ph == "scare":
                draw_bubble("BUH!", int(ev["gx"]) + 50, GB_Y - 30)
            elif ph == "laugh":
                draw_bubble("HAR HAR!", int(ev["gx"]) + 50, GB_Y - 30)
        if seed_y is not None:
            draw_art(("##", "#.", "##"), x + 7 * S, seed_y, S, COLOURS["e"])
        if think_dots:
            display.set_pen(DOT_PEN)
            for i in range(min(3, think_dots)):
                display.rectangle(int(c_x) + 11 * CS + i * 7, C_BASE_Y - 10, 4, 4)
        if bx is not None:
            # Snap to a 4px grid so it moves in chunky pixel steps
            gx, gy = int(bx) // 4 * 4 - 8, int(by) // 4 * 4 - 8
            for r, row in enumerate(BALL):
                for c, ch in enumerate(row):
                    if ch != ".":
                        display.set_pen(BALL_PEN if ch == "w" else HEART_PEN)
                        display.rectangle(gx + c * 4, gy + r * 4, 4, 4)

        for p in particles:
            kind = p[0]
            p[1] += p[3] * k
            p[2] += p[4] * k
            p[5] -= k
            if kind == "crumb":
                p[4] += 0.4 * k
                if p[2] >= GROUND - 3:
                    p[2], p[3], p[4] = GROUND - 3, 0, 0
                display.set_pen(CRUMB_PEN)
                display.rectangle(int(p[1]), int(p[2]), 3, 3)
            elif kind == "heart":
                draw_art(HEART, p[1], p[2], 3, HEART_PEN)
            elif kind == "breath":
                size = 3 if p[5] > 12 else 4 if p[5] > 6 else 5
                display.set_pen(WOOL_PEN if p[5] > 8 else ZED_PEN)
                display.rectangle(int(p[1]), int(p[2]), size, size)
            elif kind == "anger":
                draw_art(ANGER, p[1], p[2], 3, FAIL_PEN)
            elif kind == "note":
                draw_art(NOTE, p[1], p[2], 3, (ALERT_PEN, TICK_PEN, MANUAL_PEN, HEART_PEN)[int(p[1]) % 4])
            elif kind == "smoke":
                display.set_pen(WHEEL_DARK_PEN if p[5] > 12 else STAND_PEN)
                size = 6 if p[5] > 15 else 4
                display.rectangle(int(p[1]), int(p[2]), size, size)
            elif kind == "spark":
                draw_art(SPARK, p[1], p[2], 3, SPARK_PEN)
            elif kind == "zed":
                p[3] = 0.4 * math.sin(p[5] / 6)
                draw_art(ZED, p[1], p[2], 3 if p[5] > 25 else 2, ZED_PEN)
        particles = [p for p in particles if p[5] > 0]
        draw_page_dots(0)

    # LEDs: status signals (LEDS switch) beat animation lights (ANIM LIGHTS)
    status_led = None
    if settings["leds"]:
        if agent_status == "blocked":
            status_led = "alert"
        elif pipe_status == "failed":
            status_led = "failed"
        elif agent_status == "done" and c_state == "done":
            status_led = "done"
    if not settings["anim_leds"]:
        update_leds(status_led, now)
    elif ev and ev["phase"] == "scare":
        update_leds("startle", t)
    elif duo and duo["phase"] == "brawl":
        update_leds("brawl", now)
    elif duo and duo["kind"] == "dance" and duo["phase"] in ("groove", "finale"):
        update_leds("dance", now)
    elif status_led:
        update_leds(status_led, now)
    else:
        update_leds(state, t)
    presto.update()
    frame += 1
    elapsed = time.ticks_diff(time.ticks_ms(), now)
    time.sleep_ms(max(0, FRAME_MS - elapsed))
