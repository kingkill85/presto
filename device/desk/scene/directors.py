# Directors take over both actors for a while: the ball game lives here, the
# scenes for two in duo.py, the pirate's visits in pirate.py. Each director has
#   update(now, k, hp, cp)  moves both and fills in their poses; False when over
#   draw(now)               its extras on top of the scene
#   mood(now)               (LED mood, ms into it) or None
#   interruptible           may an agent asking a question end it?

import math
import random
import time

from desk import sound
from desk.gfx import BALL_PEN, HEART_PEN, display
from desk.scene.sprites import BASE_Y, C_BASE_Y, CS, GROUND, S


def walk_to(pos, target, speed, k):
    """Move pos towards target by speed px per 66 ms; returns (pos, arrived)."""
    step_px = speed * k
    if abs(target - pos) <= step_px:
        return target, True
    return pos + (step_px if target > pos else -step_px), False


def arc(u, height):
    """Height of a jump at u (0..1) of the way."""
    return int(height * math.sin(math.pi * max(0.0, min(1.0, u))))


def look_at(x, target):
    return 1 if target > x + 8 else (-1 if target < x - 8 else 0)


# --- ball game ---------------------------------------------------------------------
# They throw a ball to each other a few times; the last throw goes too high and
# whoever didn't drop it gets a point.

BALL = (".ww.", "rrrr", "wwww", ".ww.")  # 4x4, drawn with 4 px pixels


class Ball:
    interruptible = True
    HOLD_MS = 600
    FLY_MS = 1100
    scores = [0, 0]  # Messy, Clawd

    def __init__(self, messy, clawd):
        self.m, self.c = messy, clawd
        self.holder = random.choice("hc")  # "h" (hamster) or "c" (Clawd)
        self.phase = "hold"  # or "fly"
        self.t0 = time.ticks_ms()
        self.left = random.randint(3, 9)  # throws until the miss
        self.pos = None
        messy.start("ball")
        clawd.start("ball")

    def hold_point(self, who):
        if who == "h":
            return self.m.x + 8 * S, BASE_Y + 9 * S
        return self.c.x + CS, C_BASE_Y + CS

    def position(self, now):
        """Ball centre and, while flying, how far along it is (0..1)."""
        if self.phase == "hold":
            bx, by = self.hold_point(self.holder)
            return bx, by, None
        u = min(1.0, time.ticks_diff(now, self.t0) / self.FLY_MS)
        (fx, fy), (tx, ty) = self.src, self.dst
        return fx + (tx - fx) * u, fy + (ty - fy) * u - 4 * self.h * u * (1 - u), u

    def update(self, now, k, hp, cp):
        bt = time.ticks_diff(now, self.t0)
        thrower = self.holder
        catcher = "c" if thrower == "h" else "h"
        if self.phase == "hold" and bt > self.HOLD_MS:
            self.miss = self.left <= 0
            tx, ty = self.hold_point(catcher)
            if self.miss:  # too high: sails over the catcher and off the screen
                tx += 110 if catcher == "c" else -110
                ty = GROUND - 5
            self.phase, self.t0 = "fly", now
            self.src, self.dst, self.h = self.hold_point(thrower), (tx, ty), 85 if self.miss else 55
            self.left -= 1
            sound.play("toss")
        elif self.phase == "fly" and bt > self.FLY_MS:
            if self.miss:
                self.scores[0 if thrower == "h" else 1] += 1
                winner, loser = (self.m, self.c) if thrower == "h" else (self.c, self.m)
                winner.start("happy")
                loser.start("sad")
                return False
            self.holder, self.phase, self.t0 = catcher, "hold", now
            sound.play("catch")

        bx, by, u = self.pos = self.position(now)
        holding = self.phase == "hold"
        hp.look = look_at(self.m.x + 8 * S, bx)
        if holding and self.holder == "h":
            hp.paws = ((6, 10), (9, 10))
            hp.bob = 1 if time.ticks_diff(now, self.t0) > self.HOLD_MS - 200 else 0  # wind up
        elif u is not None and self.holder == "c":  # incoming
            hp.paws = ((3, 8), (12, 8))
            if u > 0.5:
                hp.eyes = "wide"
        elif u is not None and u < 0.25:
            hp.jump = 6  # just threw it
        cp.look = look_at(self.c.x + 8 * CS, bx)
        if holding and self.holder == "c":
            cp.arms = (True, False)
        elif u is not None and self.holder == "h":  # incoming
            cp.arms = (True, False)
            if u > 0.5:
                cp.eyes = "wide"
        elif u is not None and u < 0.25:
            cp.jump = 5
        return True

    def draw(self, now):
        # snapped to a 4 px grid so it moves in chunky pixel steps
        gx, gy = int(self.pos[0]) // 4 * 4 - 8, int(self.pos[1]) // 4 * 4 - 8
        for r, row in enumerate(BALL):
            for c, ch in enumerate(row):
                if ch != ".":
                    display.set_pen(BALL_PEN if ch == "w" else HEART_PEN)
                    display.rectangle(gx + c * 4, gy + r * 4, 4, 4)

    def mood(self, now):
        return None  # the "ball" state has its own
