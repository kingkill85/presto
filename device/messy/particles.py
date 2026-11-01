# Little things flying around: hearts, Zs, crumbs, smoke, sparks, notes,
# breath clouds, dirt, fluff, steam, water drops, and the seasonal ones
# (petals, leaves, a butterfly, fireflies, frost glints, fireworks).
#
# [kind, x, y, vx, vy, life, colour]; speeds and life are per 66 ms. They age
# on every page, otherwise they would pile up while another page is shown,
# but are only drawn on the scene.

import math

from messy.gfx import (ALERT_PEN, ANGER, CRUMB_PEN, EYE_PEN, FAIL_PEN, HEART, HEART_PEN, MANUAL_PEN, NOTE, SPARK,
                       SPARK_PEN, STAND_PEN, TICK_PEN, WHEEL_DARK_PEN, WOOL_PEN, ZED, ZED_PEN, display, draw_art, pen)
from messy.sprites import GROUND

DIRT_PEN = pen((122, 74, 50))
DROP_PEN = pen((90, 160, 240))
CHUNKY = {"petal": None, "leaf": None, "firefly": None, "pop": None, "dirt": DIRT_PEN, "drop": DROP_PEN,
          "fluff": WOOL_PEN, "steam": None}  # kind -> pen (None: its own colour, steam fades)

particles = []


def spawn(kind, x, y, vx, vy, life, colour=None):
    particles.append([kind, x, y, vx, vy, life, colour])


def count(kind):
    n = 0
    for p in particles:
        if p[0] == kind:
            n += 1
    return n


def update(k):
    global particles
    for p in particles:
        kind = p[0]
        p[1] += p[3] * k
        p[2] += p[4] * k
        p[5] -= k
        if kind == "crumb":  # falls and stays on the ground
            p[4] += 0.4 * k
            if p[2] >= GROUND - 3:
                p[2], p[3], p[4] = GROUND - 3, 0, 0
        elif kind == "zed":  # sways
            p[3] = 0.4 * math.sin(p[5] / 6)
        elif kind == "petal":  # flutters along
            p[4] = 0.35 * math.sin(p[5] / 5)
        elif kind == "leaf":  # tumbles down, then lies on the grass a moment
            if p[2] >= GROUND - 2:
                p[2], p[3], p[4] = GROUND - 2, 0, 0
                p[5] = min(p[5], 40)
            else:
                p[3] = 0.7 * math.sin(p[5] / 6) if p[4] > 0 else p[3]
                p[4] = min(p[4] + 0.15 * k, 0.7)  # kicked up ones come down again
        elif kind == "butterfly":
            p[4] = 0.6 * math.sin(p[5] / 9)
        elif kind == "firefly":
            p[3] = 0.4 * math.sin(p[5] / 7 + p[1] / 30)
            p[4] = 0.25 * math.sin(p[5] / 11)
        elif kind == "pop":  # firework spark: a little gravity
            p[4] += 0.06 * k
        elif kind == "dirt" or kind == "drop":  # thrown up, falls back
            p[4] += 0.35 * k
            if p[2] >= GROUND:
                p[5] = 0
        elif kind == "steam":
            p[3] = 0.3 * math.sin(p[5] / 3)
        elif kind == "fluff":
            p[4] += 0.03 * k
    particles = [p for p in particles if p[5] > 0]


def draw():
    for kind, x, y, _, _, life, colour in particles:
        x, y = int(x), int(y)
        if kind == "crumb":
            display.set_pen(CRUMB_PEN)
            display.rectangle(x, y, 3, 3)
        elif kind == "heart":
            draw_art(HEART, x, y, 3, HEART_PEN)
        elif kind == "breath":
            size = 3 if life > 12 else 4 if life > 6 else 5
            display.set_pen(WOOL_PEN if life > 8 else ZED_PEN)
            display.rectangle(x, y, size, size)
        elif kind == "anger":
            draw_art(ANGER, x, y, 3, FAIL_PEN)
        elif kind == "note":
            draw_art(NOTE, x, y, 3, (ALERT_PEN, TICK_PEN, MANUAL_PEN, HEART_PEN)[x % 4])
        elif kind == "smoke":
            display.set_pen(WHEEL_DARK_PEN if life > 12 else STAND_PEN)
            size = 6 if life > 15 else 4
            display.rectangle(x, y, size, size)
        elif kind == "spark":
            draw_art(SPARK, x, y, 3, SPARK_PEN)
        elif kind == "zed":
            draw_art(ZED, x, y, 3 if life > 25 else 2, ZED_PEN)
        elif kind in CHUNKY:  # one 4 px block on the grid
            if kind == "firefly" and not (int(life) // 5) % 3:
                continue  # blinks
            display.set_pen(colour or CHUNKY[kind] or (ZED_PEN if life > 10 else STAND_PEN))
            display.rectangle(x // 4 * 4, y // 4 * 4, 4, 4)
        elif kind == "butterfly":
            gx, gy = x // 4 * 4, y // 4 * 4
            display.set_pen(colour)
            if (int(life) // 2) % 2:  # wings open
                display.rectangle(gx - 4, gy - 4, 4, 4)
                display.rectangle(gx + 4, gy - 4, 4, 4)
            else:  # wings up
                display.rectangle(gx, gy - 8, 4, 4)
            display.set_pen(EYE_PEN)
            display.rectangle(gx, gy - 4, 4, 8)
        elif kind == "glint":  # a twinkle on the frosty ground
            gx, gy = x // 4 * 4, y // 4 * 4
            display.set_pen(WOOL_PEN)
            display.rectangle(gx, gy, 4, 4)
            if life > 4:
                display.rectangle(gx - 4, gy, 12, 4)
                display.rectangle(gx, gy - 4, 4, 12)
