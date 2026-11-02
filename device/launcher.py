# Presto launcher, pixel-art style: 240x240 (every pixel doubled), PICO-8
# palette, 12x12 pixel icons, bitmap font. Swipe left/right to change page.
# Apps are all *.py files except the ones in HIDDEN. Tapping a tile writes the
# file name to /ramfs/launch.txt and resets; on the next boot this script
# imports that app instead of drawing the menu.
import math
import os
import time

import machine
import psram

psram.mkramfs()

try:
    with open("/ramfs/launch.txt", "r") as f:
        result = f.readline()
except OSError:
    result = ""

if result.endswith(".py"):
    os.remove("/ramfs/launch.txt")
    __import__(result[:-3])

import network
import ntptime
from presto import Presto

import tz

presto = Presto(ambient_light=False, layers=1)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()

# Config and sdcard.py, not apps (other helpers live in lib/). sdcard.py is the fixed driver from
# micropython-lib PR #765, it shadows the built-in one (pimoroni/presto#79).
HIDDEN = ("main.py", "secrets.py", "ha_config.py", "sdcard.py")

# PICO-8 palette
P8 = {
    "black": (0, 0, 0), "navy": (29, 43, 83), "plum": (126, 37, 83), "forest": (0, 135, 81),
    "brown": (171, 82, 54), "slate": (95, 87, 79), "silver": (194, 195, 199), "white": (255, 241, 232),
    "red": (255, 0, 77), "orange": (255, 163, 0), "yellow": (255, 236, 39), "green": (0, 228, 54),
    "blue": (41, 173, 255), "lavender": (131, 118, 156), "pink": (255, 119, 168), "peach": (255, 204, 170),
}

# Icons: "#" main colour, "o" light colour, "+" accent colour, "." transparent.
ART = {
    "horizon": (
        "....####....",
        "..########..",
        ".##########.",
        ".##########.",
        "####o##o####",
        "oooooooooooo",
        "++++++++++++",
        "++++++++++++",
        ".++++++++++.",
        ".++++++++++.",
        "..++++++++..",
        "....++++....",
    ),
    "bomb": (
        "........o.o.",
        ".........o..",
        "........#.o.",
        ".......#....",
        "....####....",
        "..########..",
        ".###o######.",
        ".##o#######.",
        ".##########.",
        ".##########.",
        "..########..",
        "....####....",
    ),
    "bulb": (
        "....####....",
        "..##o#####..",
        ".##o#######.",
        ".##########.",
        ".##########.",
        "..########..",
        "...######...",
        "....####....",
        "....++++....",
        "....####....",
        "....++++....",
        ".....##.....",
    ),
    "cube": (
        "....oooo....",
        "..oooooooo..",
        "oooooooooooo",
        "##oooooooo++",
        "####oooo++++",
        "######++++++",
        "######++++++",
        "######++++++",
        "######++++++",
        "..####++++..",
        "....##++....",
        "............",
    ),
    "picture": (
        "############",
        "#oooooooooo#",
        "#ooooooo##o#",
        "#ooooooo##o#",
        "#oooooooooo#",
        "#oooo+ooooo#",
        "#ooo+++oooo#",
        "#oo+++++o+o#",
        "#o+++++++++#",
        "#++++++++++#",
        "#++++++++++#",
        "############",
    ),
    "maze": (
        "############",
        "#....#.....#",
        "#.##.#.###.#",
        "#.#..#...#.#",
        "#.#.####.#.#",
        "#.#......#.#",
        "#.######.#.#",
        "#......#.#.#",
        "######.#.#.#",
        "#o.....#...#",
        "#.######.###",
        "############",
    ),
    "thermometer": (
        ".....##.....",
        "....#oo#....",
        "....#oo#....",
        "....#oo#.##.",
        "....#++#....",
        "....#++#.##.",
        "....#++#....",
        "...#++++#...",
        "..#++++++#..",
        "..#++++++#..",
        "...#++++#...",
        "....####....",
    ),
    "stopwatch": (
        "....####....",
        ".....##.....",
        "...######...",
        "..#oooooo#..",
        ".#oooo#ooo#.",
        "#ooooo#oooo#",
        "#ooooo#oooo#",
        "#oooooooooo#",
        "#oooooooooo#",
        ".#oooooooo#.",
        "..#oooooo#..",
        "...######...",
    ),
    "tomato": (
        ".....++.....",
        "...++++++...",
        "..###++###..",
        ".##########.",
        "#o##########",
        "#o##########",
        "############",
        "############",
        "############",
        ".##########.",
        "..########..",
        "....####....",
    ),
    "clock": (
        "....####....",
        "..##oooo##..",
        ".#oooo#ooo#.",
        "#ooooo#oooo#",
        "#ooooo#oooo#",
        "#ooooo#oooo#",
        "#ooooo###oo#",
        "#oooooooooo#",
        "#oooooooooo#",
        ".#oooooooo#.",
        "..##oooo##..",
        "....####....",
    ),
    "speech": (
        "............",
        ".##########.",
        "#oooooooooo#",
        "#o######ooo#",
        "#oooooooooo#",
        "#o####o###o#",
        "#oooooooooo#",
        "#o#####oooo#",
        "#oooooooooo#",
        ".#####o####.",
        "....##......",
        "............",
    ),
    "flower": (
        "..##....##..",
        ".####..####.",
        ".####oo####.",
        "..##oooo##..",
        "..##oooo##..",
        ".####oo####.",
        ".####..####.",
        "..##.++.##..",
        ".....++.....",
        "..+++++.....",
        "....+++.....",
        ".....++.....",
    ),
    "unknown": (
        "############",
        "#oooooooooo#",
        "#ooo####ooo#",
        "#oo##oo##oo#",
        "#oooooo##oo#",
        "#ooooo##ooo#",
        "#oooo##oooo#",
        "#oooo##oooo#",
        "#oooooooooo#",
        "#oooo##oooo#",
        "#oooooooooo#",
        "############",
    ),
}

# file: (label, icon, tile, "#", "o", "+")
APPS = {
    "attitude_indicator.py": ("Horizont", "horizon", "navy", "blue", "white", "brown"),
    "awesome_game.py": ("Spiel", "bomb", "slate", "black", "white", "orange"),
    "cheerlights_bulb.py": ("Lampe", "bulb", "slate", "yellow", "white", "silver"),
    "cubes.py": ("Wuerfel", "cube", "plum", "pink", "white", "red"),
    "immich_frame.py": ("Immich", "flower", "lavender", "pink", "yellow", "green"),
    "image_gallery.py": ("Fotos", "picture", "brown", "yellow", "blue", "green"),
    "random_maze.py": ("Labyrinth", "maze", "forest", "green", "yellow", "green"),
    "sensor-stick-temperature.py": ("Klima", "thermometer", "navy", "white", "silver", "red"),
    "stop_watch.py": ("Stoppuhr", "stopwatch", "plum", "orange", "white", "orange"),
    "tomato.py": ("Pomodoro", "tomato", "forest", "red", "pink", "green"),
    "vector_clock_full.py": ("Analoguhr", "clock", "brown", "slate", "white", "slate"),
    "word_clock.py": ("Wortuhr", "speech", "navy", "blue", "white", "blue"),
}
DEFAULT = ("unknown", "slate", "orange", "yellow", "orange")

# Grid geometry, in 240x240 pixels
COLS = 3
ROWS = 3
PER_PAGE = COLS * ROWS
TILE = 62
GAP = 6
TOP = 24
LEFT = (WIDTH - (COLS * TILE + (COLS - 1) * GAP)) // 2
SCALE = 3  # icon pixel size
ICON = 12 * SCALE


def pen(rgb, k=1.0):
    return display.create_pen(*(min(255, int(c * k)) for c in rgb))


BACKGROUND = pen(P8["black"])
STAR = pen(P8["navy"])
TEXT = pen(P8["white"])
DIM = pen(P8["slate"])
ONLINE = pen(P8["green"])
OUTLINE = pen(P8["black"])

display.set_font("bitmap8")

# Fixed pseudo-random starfield behind the tiles
STARS = [((i * 97) % WIDTH, (i * 61 + i * i * 7) % HEIGHT) for i in range(60)]


class App:
    def __init__(self, index, file):
        self.file = file
        name = " ".join(w[0].upper() + w[1:] for w in file[:-3].replace("_", " ").replace("-", " ").split())
        label, art, tile, main, light, accent = APPS.get(file, (name,) + DEFAULT)
        self.label = label
        self.art = ART[art]
        self.colours = {"#": pen(P8[main]), "o": pen(P8[light]), "+": pen(P8[accent])}
        self.bg = pen(P8[tile])
        self.hi = pen(P8[tile], 1.6)
        self.lo = pen(P8[tile], 0.55)

        self.page = index // PER_PAGE
        slot = index % PER_PAGE
        self.x = LEFT + (slot % COLS) * (TILE + GAP)
        self.y = TOP + (slot // COLS) * (TILE + GAP)

    def hit(self, x, y):
        return self.x <= x < self.x + TILE and self.y <= y < self.y + TILE

    def draw(self, pressed):
        x, y, s = self.x, self.y, TILE
        # Outline with cut corners
        display.set_pen(OUTLINE)
        display.rectangle(x + 1, y, s - 2, s)
        display.rectangle(x, y + 1, s, s - 2)
        # Face, 2px bevel: light top/left, dark bottom/right (swapped when pressed)
        top, bottom = (self.lo, self.hi) if pressed else (self.hi, self.lo)
        display.set_pen(bottom)
        display.rectangle(x + 1, y + 1, s - 2, s - 2)
        display.set_pen(top)
        display.rectangle(x + 1, y + 1, s - 4, s - 4)
        display.set_pen(self.bg)
        display.rectangle(x + 3, y + 3, s - 6, s - 6)

        d = 1 if pressed else 0
        ix = x + (s - ICON) // 2 + d
        iy = y + 7 + d
        for row, line in enumerate(self.art):
            for col, c in enumerate(line):
                if c != ".":
                    display.set_pen(self.colours[c])
                    display.rectangle(ix + col * SCALE, iy + row * SCALE, SCALE, SCALE)

        w = display.measure_text(self.label, 1)
        display.set_pen(OUTLINE)
        display.text(self.label, x + (s - w) // 2 + d + 1, y + 47 + d + 1, -1, 1)
        display.set_pen(TEXT)
        display.text(self.label, x + (s - w) // 2 + d, y + 47 + d, -1, 1)

    def launch(self):
        with open("/ramfs/launch.txt", "w") as f:
            f.write(self.file)
        display.set_pen(BACKGROUND)
        display.clear()
        presto.update()
        machine.reset()


files = sorted(f for f in os.listdir() if f.endswith(".py") and f not in HIDDEN)
apps = [App(i, f) for i, f in enumerate(files)]
pages = max(1, math.ceil(len(apps) / PER_PAGE))

for i in range(7):
    presto.set_led_rgb(i, 0, 0, 0)

# Connect in the background; the menu stays usable while it happens.
wlan = network.WLAN(network.STA_IF)
time_synced = False
try:
    from secrets import WIFI_PASSWORD, WIFI_SSID
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
except Exception:
    pass


def draw_status(online):
    if time_synced:
        t = tz.localtime()
        display.set_pen(TEXT)
        display.text("%02d:%02d" % (t[3], t[4]), LEFT + 1, 8, -1, 1)
    # Signal bars, right-aligned with the grid
    x = WIDTH - LEFT - 15
    for i in range(4):
        h = 2 + i * 2
        display.set_pen(ONLINE if online else DIM)
        display.rectangle(x + i * 4, 15 - h, 3, h)


def draw_dots():
    if pages < 2:
        return
    y = TOP + ROWS * TILE + (ROWS - 1) * GAP + 5
    x0 = WIDTH // 2 - (pages - 1) * 5
    for p in range(pages):
        display.set_pen(TEXT if p == page else DIM)
        display.rectangle(x0 + p * 10 - 1, y, 3, 3)


def draw(online):
    display.set_pen(BACKGROUND)
    display.clear()
    display.set_pen(STAR)
    for sx, sy in STARS:
        display.pixel(sx, sy)
    draw_status(online)
    for app in apps:
        if app.page == page:
            app.draw(app is pressed_app)
    draw_dots()
    presto.update()


page = 0
touch = presto.touch
start = None
last = None
pressed_app = None
shown = None  # state of the last drawn frame; redraw only when it changes

while True:
    online = wlan.isconnected()
    if not time_synced and online:
        try:
            ntptime.settime()
            time_synced = True
        except OSError:
            pass

    touch.poll()
    if touch.state:
        last = (touch.x, touch.y)
        if start is None:
            start = last
            for app in apps:
                if app.page == page and app.hit(*start):
                    pressed_app = app
        elif abs(last[0] - start[0]) > 6:
            pressed_app = None
    elif start is not None:
        dx = last[0] - start[0]
        if dx < -30 and page < pages - 1:
            page += 1
        elif dx > 30 and page > 0:
            page -= 1
        elif pressed_app and pressed_app.hit(*last):
            pressed_app.launch()
        start = None
        pressed_app = None

    minute = tz.localtime()[4] if time_synced else -1
    state = (page, pressed_app, online, time_synced, minute)
    if state != shown:
        draw(online)
        shown = state
    else:
        time.sleep_ms(15)
