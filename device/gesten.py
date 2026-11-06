# Gesten: shows the APDS-9960 (0x39) live. Swipes over the sensor light up a
# big arrow; around it the four photodiodes, below proximity and colour.
import time

from desk.gfx import display, draw_art, pen, presto, DIM_PEN, TEXT_PEN
from sensor_app import Exit, bus, header, leave, pace, panel
from apds9960 import APDS9960, UP, DOWN, LEFT, RIGHT

ICON = ("#.#.#", "#.#.#", "#####", "#####", ".###.")
ACCENT = pen((255, 119, 168))
LIT = pen((255, 236, 39))
FADED = pen((131, 118, 156))
DIODE = pen((41, 173, 255))
PROX = pen((0, 228, 54))
DARK = pen((15, 22, 45))
WARN = pen((255, 236, 39))

ARROW_UP = (
    "...#...",
    "..###..",
    ".#####.",
    "#######",
    "..###..",
    "..###..",
    "..###..",
)


def _rotate(art):
    """90 degrees clockwise."""
    n = len(art)
    return tuple("".join(art[n - 1 - r][c] for r in range(n)) for c in range(n))


ARROW_RIGHT = _rotate(ARROW_UP)
ARROW_DOWN = _rotate(ARROW_RIGHT)
ARROW_LEFT = _rotate(ARROW_DOWN)
ARROWS = {UP: ARROW_UP, DOWN: ARROW_DOWN, LEFT: ARROW_LEFT, RIGHT: ARROW_RIGHT}
NAMES = {UP: "HOCH", DOWN: "RUNTER", LEFT: "LINKS", RIGHT: "RECHTS"}
FLASH_MS = 1500

CX, CY = 120, 104  # centre of the arrow area


def draw(sensor, last, last_at, count, now):
    header("GESTEN", ACCENT, ICON)
    panel(12, 44, 216, 120)
    if not sensor.connected:
        display.set_pen(WARN)
        display.text("Sensor fehlt", 50, 96, -1, 2)
        return
    # The four photodiodes: bars on each side of the arrow (8 bit samples)
    u, d, l, r = sensor.udlr
    display.set_pen(DIODE)
    display.rectangle(CX - 24, 52, 48 * u // 255 // 4 * 4, 4)
    display.rectangle(CX - 24, 152, 48 * d // 255 // 4 * 4, 4)
    display.rectangle(20, CY - 24, 4, 48 * l // 255 // 4 * 4)
    display.rectangle(216, CY - 24, 4, 48 * r // 255 // 4 * 4)
    # The last swipe, bright for a moment, then faded
    if last is None:
        display.set_pen(DIM_PEN)
        msg = "Wisch drueber!"
        display.text(msg, CX - display.measure_text(msg, 2) // 2, CY - 8, -1, 2)
    else:
        fresh = time.ticks_diff(now, last_at) < FLASH_MS
        draw_art(ARROWS[last], CX - 28, CY - 36, 8, LIT if fresh else FADED)
        name = NAMES[last]
        display.set_pen(TEXT_PEN if fresh else DIM_PEN)
        display.text(name, CX - display.measure_text(name, 1) // 2, CY + 26, -1, 1)
    display.set_pen(DIM_PEN)
    display.text("%d" % count, 200, 140, -1, 1)
    # Proximity
    panel(12, 168, 104, 60)
    display.set_pen(DIM_PEN)
    display.text("Naehe", 20, 174, -1, 1)
    display.set_pen(DARK)
    display.rectangle(20, 188, 88, 12)
    display.set_pen(PROX)
    display.rectangle(20, 188, 88 * sensor.proximity // 255 // 4 * 4, 12)
    display.set_pen(TEXT_PEN)
    display.text("%d" % sensor.proximity, 20, 206, -1, 2)
    # Colour: the measured light, normalised to its brightest channel
    panel(124, 168, 104, 60)
    display.set_pen(DIM_PEN)
    display.text("Farbe", 132, 174, -1, 1)
    top = max(sensor.red, sensor.green, sensor.blue, 1)
    swatch = pen((255 * sensor.red // top, 255 * sensor.green // top, 255 * sensor.blue // top))
    display.set_pen(DARK)
    display.rectangle(130, 186, 32, 36)
    display.set_pen(swatch)
    display.rectangle(132, 188, 28, 32)
    display.set_pen(TEXT_PEN)
    display.text("Licht", 168, 190, -1, 1)
    display.text("%d" % sensor.clear, 168, 204, -1, 2)


def main():
    i2c = bus()
    sensor = APDS9960(i2c)
    exit_ = Exit(i2c)
    last, last_at, count = None, 0, 0
    while True:
        now = time.ticks_ms()
        if exit_.back(now):
            leave(sensor)
        sensor.poll(now)
        if sensor.gesture is not None:
            last, last_at = sensor.gesture, now
            count += 1
        draw(sensor, last, last_at, count, now)
        presto.update()
        pace(now)


main()
