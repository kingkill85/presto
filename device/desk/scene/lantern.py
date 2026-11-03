"""Guybrush brings a lantern; both actors keep their own status and poses."""
import time
from desk.gfx import display, draw_colour_art, pen, snap
from desk.scene.directors import walk_to
from desk.scene.sprites import GB_HAND, GB_HAND_L, GB_Y, draw_guybrush, walk_frame

LANTERN = ('..hh..', '.h..h.', '.hhhh.', '.hyyh.', '.hwwh.', '.hyyh.', '.hhhh.')
PENS = {'h': pen((171, 82, 54)), 'y': pen((255, 236, 39)), 'w': pen((255, 241, 232))}
GLOW = (pen((95, 67, 37)), pen((145, 103, 47)), pen((206, 153, 70)))


class Lantern:
    def __init__(self, now, messy, clawd):
        self.started = now
        self.arrived = None
        self.x = -76
        self.leaving = False
        self.m, self.c = messy, clawd

    def update(self, now, k):
        elapsed = time.ticks_diff(now, self.started)
        if self.arrived is not None and time.ticks_diff(now, self.arrived) >= 7000:
            self.leaving = True
        self.x, there = walk_to(self.x, -76 if self.leaving else 80, 3.5, k)
        if there:
            if self.leaving:
                return False
            if self.arrived is None:
                self.arrived = now
        return elapsed < 18000

    def draw(self, now):
        elapsed = time.ticks_diff(now, self.started)
        walking = self.arrived is None or self.leaving
        legs, arms, bob, hem, hair = walk_frame(elapsed) if walking else ('stand', 'down', 0, 0, 0)
        lx = snap(self.x + (GB_HAND_L if self.leaving else GB_HAND[0]))
        ly = snap(GB_Y + GB_HAND[1] + bob)
        if self.arrived is not None and not self.leaving:
            # Warm, dithered fans behind both figures, never over status icons.
            for actor in (self.m, self.c):
                target = actor.x + 32
                for i in range(1, 9):
                    x = snap(lx + (target - lx) * i / 8)
                    width = 4 + (i // 3) * 4
                    display.set_pen(GLOW[2 - i // 4])
                    for j in (-1, 0, 1):
                        display.rectangle(x, snap(ly + j * width), 4, 4)
            display.set_pen(GLOW[(elapsed // 220) % 2])
            display.rectangle(lx - 8, ly + 4, 28, 24)
        draw_guybrush(self.x, flip=self.leaving, legs=legs, arms=arms,
                      bob=bob, hem=hem, hair=hair, mouth=1 if not walking else 0,
                      front=not walking)
        draw_colour_art(LANTERN, PENS, lx - 8, ly)
