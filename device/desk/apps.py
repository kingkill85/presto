# The other apps on the device, for the apps page (drawn in pages.py).
# launch() writes the file name to /ramfs/launch.txt and resets; main.py then
# starts that app instead of the start screen (once: a reset brings it back).

import os

import machine

from desk import sound
from desk.gfx import pen, presto

# Config and helpers in the root, not apps. sdcard.py stays here since the
# frozen built-in sdcard would shadow it in lib/.
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
    "gamepad": (
        "............",
        "..########..",
        ".##########.",
        "####o####+##",
        "###ooo##+###",
        "####o#######",
        "#####..#####",
        "####....####",
        ".##......##.",
        "............",
        "............",
        "............",
    ),
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

# file: (label, icon, "#", "o", "+")
APPS = {
    "gb.py": ("Retro", "gamepad", "lavender", "white", "pink"),
    "scumm.py": ("SCUMM", "gamepad", "orange", "white", "yellow"),
    "attitude_indicator.py": ("Horizont", "horizon", "blue", "white", "brown"),
    "awesome_game.py": ("Spiel", "bomb", "black", "white", "orange"),
    "cheerlights_bulb.py": ("Lampe", "bulb", "yellow", "white", "silver"),
    "cubes.py": ("Wuerfel", "cube", "pink", "white", "red"),
    "immich_frame.py": ("Immich", "flower", "pink", "yellow", "green"),
    "image_gallery.py": ("Fotos", "picture", "yellow", "blue", "green"),
    "random_maze.py": ("Labyrinth", "maze", "green", "yellow", "green"),
    "sensor-stick-temperature.py": ("Klima", "thermometer", "white", "silver", "red"),
    "stop_watch.py": ("Stoppuhr", "stopwatch", "orange", "white", "orange"),
    "tomato.py": ("Pomodoro", "tomato", "red", "pink", "green"),
    "vector_clock_full.py": ("Analoguhr", "clock", "slate", "white", "slate"),
    "word_clock.py": ("Wortuhr", "speech", "blue", "white", "blue"),
}
DEFAULT = ("unknown", "slate", "yellow", "orange")

MAX = 12  # what fits on the page


def _label(file):
    return " ".join(w[0].upper() + w[1:] for w in file[:-3].replace("_", " ").replace("-", " ").split())


def _find():
    p8 = {name: pen(rgb) for name, rgb in P8.items()}
    found = []
    for f in sorted(os.listdir("/")):
        if f.endswith(".py") and f not in HIDDEN:
            label, art, main, light, accent = APPS.get(f, (_label(f),) + DEFAULT)
            pens = {"#": p8[main], "o": p8[light], "+": p8[accent]}
            found.append((f, label[:11], ART[art], pens))
    return found[:MAX]


_apps = None


def get():
    """(file, label, art, pens) per app, found on the first visit of the page
    (not at boot, that would cost ~180 ms). New apps show up after a reset."""
    global _apps
    if _apps is None:
        _apps = _find()
    return _apps


def launch(file):
    sound.stop_music()
    for led in range(7):
        presto.set_led_rgb(led, 0, 0, 0)
    with open("/ramfs/launch.txt", "w") as f:
        f.write(file)
    machine.reset()
