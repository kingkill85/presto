# Directors take over both actors for a while: the ball game and the pirate
# visit live here, the scenes for two in duo.py. Each director has
#   update(now, k, hp, cp)  moves both and fills in their poses; False when over
#   draw(now)               its extras on top of the scene
#   mood(now)               (LED mood, ms into it) or None
#   interruptible           may an agent asking a question end it?

import math
import random
import time

from desk import sound
from desk.gfx import BALL_PEN, HEART_PEN, WIDTH, display, draw_bubble
from desk.scene.actors import RUN, WALK
from desk.scene.sprites import (BASE_Y, C_BASE_Y, C_HOME_X, C_MAX_X, CS, GB, GB_W, GB_Y, GROUND, HOME_X, S, draw_guybrush,
                           walk_frame)


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


# --- pirate visit ---------------------------------------------------------------------
# Every few minutes a wannabe pirate walks in, shouts "BUH!" and scares both
# off the screen. Phases: enter, scare, flee, laugh, leave, pause, return.

BACK_X = 76  # where the hamster backs off to when the pirate walks in
_next_visit = time.ticks_add(time.ticks_ms(), random.randint(60000, 180000))


def visit_due(now):
    return time.ticks_diff(now, _next_visit) > 0


class Visit:
    interruptible = False

    def __init__(self, messy, clawd, now):
        self.m, self.c = messy, clawd
        self.phase, self.t0 = "enter", now
        self.gx = -GB_W * GB - 4  # the pirate's x
        sound.play_music(sound.guybrush_tune())
        messy.start("event")
        clawd.start("event")

    def go(self, phase, now):
        self.phase, self.t0 = phase, now

    def update(self, now, k, hp, cp):
        global _next_visit
        m, c = self.m, self.c
        ph, et = self.phase, time.ticks_diff(now, self.t0)
        if ph == "enter":  # he walks in, the two nervously back away to the right
            self.gx += 2.5 * k
            m.x = min(BACK_X, m.x + 2 * k)
            c.x = min(C_MAX_X, c.x + 1.2 * k)
            if self.gx >= 4:
                self.go("scare", now)
        elif ph == "scare" and et > 1300:
            self.go("flee", now)
        elif ph == "flee":
            m.x += 8 * k
            c.x += 7 * k
            if m.x > WIDTH + 10 and c.x > WIDTH + 10:
                self.go("laugh", now)
        elif ph == "laugh" and et > 1800:
            self.go("leave", now)
        elif ph == "leave":
            self.gx -= 2.5 * k
            if self.gx < -GB_W * GB - 4:
                self.go("pause", now)
        elif ph == "pause" and et > 2000:
            self.go("return", now)
        elif ph == "return":
            m.x = max(HOME_X, m.x - 2.5 * k)
            c.x = max(C_HOME_X, c.x - 2.5 * k)
            if m.x == HOME_X and c.x == C_HOME_X:
                _next_visit = time.ticks_add(now, random.randint(120000, 300000))
                m.start("idle")
                c.start("idle")
                return False

        ph, et = self.phase, time.ticks_diff(now, self.t0)
        if ph == "enter":
            hp.look = cp.look = -1
            if self.gx > -40:
                hp.eyes = cp.eyes = "wide"
            if m.x < BACK_X:
                hp.step, hp.jump = WALK[(m.elapsed(now) // 110) % 4]
            if c.x < C_MAX_X:
                cp.step, cp.jump = WALK[(c.elapsed(now) // 120) % 4]
        elif ph == "scare":
            hp.eyes = cp.eyes = "wide"
            hp.paws = ((3, 8), (12, 8))
            hp.jump = int(20 * math.sin(math.pi * min(1, et / 400)))
            cp.arms = (True, True)
            cp.jump = int(16 * math.sin(math.pi * min(1, max(0, et - 100) / 400)))
        elif ph == "flee":
            hp.eyes = cp.eyes = "wide"
            hp.look = cp.look = 1
            hp.step, hp.jump = RUN[(et // 70) % 4]
            cp.step, cp.jump = RUN[(et // 70) % 4]
        elif ph == "return":
            hp.look = cp.look = -1
            if m.x > HOME_X:
                hp.step, hp.jump = WALK[(et // 110) % 4]
            if c.x > C_HOME_X:
                cp.step, cp.jump = WALK[(et // 120) % 4]
        return True

    def draw(self, now):
        ph, et = self.phase, time.ticks_diff(now, self.t0)
        if ph not in ("enter", "scare", "flee", "laugh", "leave"):
            return
        legs, arms, bob, hem, hair, mouth = "stand", "down", 0, 0, 0, 0
        if ph in ("enter", "leave"):
            legs, arms, bob, hem, hair = walk_frame(et)
        elif ph == "scare":
            arms, mouth = "up", 2  # shouting
            bob = -3 if et < 150 else 0
            hair = 1 if et < 300 else 0
        elif ph == "laugh":
            beat = (et // 200) % 2 == 0
            bob, mouth = (-2, 2) if beat else (0, 1)  # shoulders shake, mouth wide open
        draw_guybrush(self.gx, flip=ph == "leave", legs=legs, arms=arms, mouth=mouth, bob=bob, hem=hem, hair=hair)
        if ph == "scare":
            draw_bubble("BUH!", int(self.gx) + 50, GB_Y - 30)
        elif ph == "laugh":
            draw_bubble("HAR HAR!", int(self.gx) + 50, GB_Y - 30)

    def mood(self, now):
        if self.phase == "scare":
            return "startle", time.ticks_diff(now, self.t0)
        return None
