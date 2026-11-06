"""Shared frame of the sensor apps (Abstand, Gesten) in the desk's look.

Uses the desk's 240x240 screen from desk.gfx. Tapping the header or B on the
pad resets back to the desk, like every app started from the apps page.
"""

import time

import machine
from machine import I2C, Pin

from gamepad import B, Gamepad
from desk.gfx import display, draw_art, pen, presto, touch, TEXT_PEN, DIM_PEN

BG = pen((29, 43, 83))
TILE = pen((45, 60, 110))
SHADE = pen((15, 22, 45))
SPARKLES = tuple((((i * 53 + 17) % 232) // 4 * 4, (40 + (i * 71) % 190) // 4 * 4) for i in range(14))
BACK = ("..#", ".#.", "#..", ".#.", "..#")


def header(title, colour, art):
    display.set_pen(BG)
    display.clear()
    display.set_pen(TILE)
    for x, y in SPARKLES:
        display.rectangle(x, y, 4, 4)
    draw_art(BACK, 8, 18, 3, DIM_PEN)
    draw_art(art, 26, 14, 3, colour)
    display.set_pen(SHADE)
    display.text(title, 52, 18, -1, 2)
    display.set_pen(TEXT_PEN)
    display.text(title, 50, 16, -1, 2)


def panel(x, y, w, h):
    display.set_pen(TILE)
    display.rectangle(x, y, w, h)
    display.set_pen(BG)
    for cx, cy in ((x, y), (x + w - 2, y), (x, y + h - 2), (x + w - 2, y + h - 2)):
        display.rectangle(cx, cy, 2, 2)


def bus():
    return I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)


class Exit:
    """Watches touch and pad; back() is true once the user wants to leave."""

    def __init__(self, bus):
        self.pad = Gamepad(bus)
        self.was = False
        self.start = None

    def back(self, now):
        self.pad.poll(now)
        if self.pad.pressed & B:
            return True
        touch.poll()
        if touch.state:
            if not self.was:
                self.start = (touch.x, touch.y)
            self.was = True
            return False
        tapped = self.was and self.start is not None and self.start[1] < 44
        self.was = False
        return tapped


def leave(*sensors):
    for s in sensors:
        s.stop()
    display.set_pen(BG)
    display.clear()
    presto.update()
    machine.reset()


def pace(start, ms=33):
    """Sleep the rest of a ~30 fps frame."""
    left = ms - time.ticks_diff(time.ticks_ms(), start)
    if left > 0:
        time.sleep_ms(left)
