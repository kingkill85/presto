# Scenes for two: Messy and Clawd do something together. Each kind runs
# through its phases, moving both and posing them, plus extra effects (dust
# cloud, dizzy stars, a seed). In the end both walk back home.

import math
import random
import time

from desk import sound
from desk.gfx import (ALERT_PEN, CLAWD_PEN, EYE_PEN, FUR_PEN, SEED_ART, SEED_PEN, STAND_PEN, WHEEL_PEN, WIDTH,
                       display, draw_bubble, draw_colour_art, pen,
                       draw_alert_sign, draw_art)
from desk.prefs import settings
from desk.scene import seasons
from desk.scene.actors import RUN, WALK
from desk.scene.directors import arc, walk_to
from desk.scene.particles import spawn
from desk.scene.sprites import BASE_Y, C_BASE_Y, C_HOME_X, CS, GROUND, HOME_X, S

KINDS = (("fight", 3), ("chase", 3), ("dance", 2), ("snack", 2), ("leap", 2), ("hide", 2), ("season", 3),
         ("plane", 2), ("magic", 2), ("mirror", 2))
# (kind, weight)
MEET_X, C_MEET_X = 74, 128  # standing nose to nose


def random_kind():
    r = random.uniform(0, sum(w for _, w in KINDS))
    for kind, w in KINDS:
        r -= w
        if r <= 0:
            return kind
    return kind


class Duo:
    interruptible = True

    def __init__(self, messy, clawd, kind=None):
        self.m, self.c = messy, clawd
        self.kind = kind or random_kind()
        self.phase = "start"
        self.t0 = time.ticks_ms()
        self.spawn = -100000
        self.fx = []  # effects of this frame: (kind, x, y)
        messy.start("duo")
        clawd.start("duo")

    # helpers for the scenes

    def go(self, phase):
        self.phase = phase
        self.t0 = self.now
        self.spawn = -100000

    def every(self, ms):
        """True once every ms milliseconds of the current phase."""
        if self.t - self.spawn >= ms:
            self.spawn = self.t
            return True
        return False

    def walking(self, p, ms=110):
        p.step, p.jump = WALK[(self.t // ms) % 4]

    def running(self, p):
        p.step, p.jump = RUN[(self.t // 70) % 4]

    def move(self, actor, target, speed):
        """Walk an actor towards target; True once there."""
        actor.x, there = walk_to(actor.x, target, speed, self.k)
        return there

    def meet(self, next_phase, hp, cp, speed=2.5):
        """Walk up to each other, then go on with next_phase."""
        a = self.move(self.m, MEET_X, speed)
        b = self.move(self.c, C_MEET_X, speed)
        if not a:
            self.walking(hp)
        if not b:
            self.walking(cp, 120)
        if a and b:
            self.go(next_phase)

    # the director interface

    def update(self, now, k, hp, cp):
        self.now, self.k = now, k
        self.t = time.ticks_diff(now, self.t0)
        self.fx = []
        hp.look, cp.look = 1, -1  # facing each other
        if self.phase == "home":
            return self.home(hp, cp)
        getattr(self, self.kind)(self.phase, self.t, hp, cp)
        return True

    def mood(self, now):
        if self.phase == "brawl":
            return "brawl", now
        if self.kind == "dance" and self.phase in ("groove", "finale"):
            return "dance", now
        return None

    def home(self, hp, cp):
        """Everyone back to their spot, then the scene ends."""
        m, c = self.m, self.c
        a = self.move(m, HOME_X, 2.5)
        b = self.move(c, C_HOME_X, 2.0)
        hp.look = -1 if m.x > HOME_X else 0
        cp.look = 1 if c.x < C_HOME_X else -1
        if not a:
            self.walking(hp)
        if not b:
            self.walking(cp, 120)
        if a and b:
            m.start("idle")
            c.start("idle")
            return False
        return True

    # the scenes

    def fight(self, ph, t, hp, cp):
        """Argue, brawl in a dust cloud, fly apart, sulk, make up with a hug."""
        m, c = self.m, self.c
        if ph == "start":
            self.meet("argue", hp, cp)
        elif ph == "argue":  # angry faces, taking turns to puff up
            hp.eyes = cp.eyes = "angry"
            beat = (t // 300) % 2
            hp.jump = 5 if beat == 0 else 0
            cp.jump = 5 if beat == 1 else 0
            cp.arms = (beat == 1, False)
            if self.every(350):
                sound.play("grr", 0.08)
                if (t // 350) % 2 == 0:
                    spawn("anger", m.x + 12 * S, BASE_Y - 14, 0, -0.4, 14)
                else:
                    spawn("anger", c.x + 10 * CS, C_BASE_Y - 14, 0, -0.4, 14)
            if t > 2200:
                self.go("brawl")
        elif ph == "brawl":  # a cloud of dust with flying fists
            hp.hide = cp.hide = True
            self.fx.append(("cloud", (m.x + 8 * S + c.x + 8 * CS) // 2, 0))
            if self.every(260):
                sound.play(("pow", "bam", "pow", "bonk")[(t // 260) % 4])
                spawn("spark", (m.x + c.x) // 2 + 40 + random.randint(-50, 50), GROUND - 60 + random.randint(-30, 20),
                      random.uniform(-2, 2), random.uniform(-2.5, -0.5), 12)
            if t > 2400:
                self.go("apart")
        elif ph == "apart":  # thrown apart
            if self.every(10000):
                sound.play("whoosh")
            self.move(m, 24, 9)
            self.move(c, C_HOME_X + 10, 9)
            hp.eyes = cp.eyes = "wide"
            hp.jump, cp.jump = arc(t / 600, 22), arc(t / 600, 18)
            if t > 650:
                self.go("dizzy")
        elif ph == "dizzy":  # stars circling their heads
            hp.eyes = "closed" if (t // 300) % 2 else "wide"
            cp.eyes = "closed" if (t // 300) % 2 == 0 else "open"
            hp.look = cp.look = 0
            hp.bob = (t // 250) % 2
            self.fx.append(("stars", m.x + 8 * S, BASE_Y - 4))
            self.fx.append(("stars", c.x + 8 * CS, C_BASE_Y - 6))
            if t > 1800:
                self.go("sulk")
        elif ph == "sulk":  # turned away from each other
            hp.look, cp.look = -1, 1
            hp.bob, cp.eyes = 1, "sad"
            if t > 1600:
                self.go("makeup")
        elif ph == "makeup":  # Clawd comes over first, the hamster turns round
            b = self.move(c, C_MEET_X, 1.4)
            if not b:
                self.walking(cp, 160)
            if t > 900:
                a = self.move(m, MEET_X, 1.6)
                if not a:
                    self.walking(hp, 150)
            else:
                hp.look, hp.bob = -1, 1
                a = False
            if a and b:
                self.go("hug")
        elif ph == "hug":
            hp.eyes = cp.eyes = "happy"
            hp.blush = True
            hp.paws = ((13, 8), (14, 7))
            cp.arms = (3, False)
            hp.bob = cp.bob = (t // 500) % 2
            if t < 100 and self.every(10000):
                sound.play("aww")
            if self.every(320):
                spawn("heart", m.x + 14 * S + random.randint(-8, 8), BASE_Y - 4, random.uniform(-0.4, 0.4), -1.4, 24)
            if t > 2400:
                self.go("home")

    def chase(self, ph, t, hp, cp):
        """Clawd sneaks up, they run around the world, pant, high five."""
        m, c = self.m, self.c
        if ph == "start":  # Clawd sneaks up
            b = self.move(c, m.x + 70, 1.0)
            cp.eyes = "down"
            self.walking(cp, 200)
            hp.look, hp.sniff = 0, (t // 75) % 2 == 0
            if b:
                self.go("spot")
        elif ph == "spot":
            hp.eyes = cp.eyes = "wide"
            hp.jump = arc(t / 400, 16)
            self.fx.append(("alert", m.x + 6 * S, BASE_Y - hp.jump - 30))
            if t > 700:
                self.go("flee")
        elif ph == "flee":  # off to the left...
            hp.look = cp.look = -1
            hp.eyes = "wide"
            a = self.move(m, -80, 7)
            self.running(hp)
            if t > 250:
                b = self.move(c, -100, 6.2)
                self.running(cp)
            else:
                b = False
            if a and b:
                m.x, c.x = WIDTH + 10, WIDTH + 110  # ...and back in from the right
                self.go("back")
        elif ph == "back":
            hp.look = cp.look = -1
            a = self.move(m, HOME_X, 6)
            b = self.move(c, C_HOME_X, 5.6)
            if not a:
                self.running(hp)
            if not b:
                self.running(cp)
            if a and b:
                self.go("pant")
        elif ph == "pant":
            hp.eyes = cp.eyes = "closed"
            hp.mouth = 1 + (t // 150) % 2
            hp.bob = cp.bob = (t // 160) % 2
            hp.look = cp.look = 0
            if t > 1500:
                self.go("meet")
        elif ph == "meet":
            hp.eyes = cp.eyes = "happy"
            self.meet("highfive", hp, cp)
        elif ph == "highfive":
            hp.eyes = cp.eyes = "happy"
            hp.jump, cp.jump = arc(t / 700, 18), arc(t / 700, 16)
            hp.paws = ((14, 6), (14, 5))
            cp.arms = (True, False)
            if 330 < t < 400 and self.every(500):
                for _ in range(6):
                    spawn("spark", m.x + 15 * S, BASE_Y - 10, random.uniform(-2, 2), random.uniform(-2.5, 0), 14)
            if t > 1200:
                self.go("home")

    def dance(self, ph, t, hp, cp):
        """Dance in turns, to dance.rtttl on the Presto if it's there."""
        m, c = self.m, self.c
        if ph == "start":
            tune, beat_ms = sound.load_rtttl("dance.rtttl") if settings["music"] else (None, None)
            self.beat, self.length = 420, 6500
            if tune:
                sound.play_music(tune)
                self.beat = beat_ms
                self.length = min(25000, sum(ms for _, ms in tune))
            self.go("groove")
        elif ph == "groove":
            bm = self.beat
            beat = t // bm
            on = beat % 2 == 0
            hp.eyes = cp.eyes = "happy"
            hp.look = cp.look = 1 if (beat // 2) % 2 else -1
            hp.jump = 9 if on and t % bm < bm * 6 // 10 else 0
            cp.jump = 9 if not on and t % bm < bm * 6 // 10 else 0
            hp.bob = 1 if on and t % bm >= bm * 7 // 10 else 0
            hp.paws = ((3, 8), (12, 7)) if on else ((3, 7), (12, 8))
            cp.arms = (on, not on)
            if self.every(bm):
                spawn("note", random.choice((m.x + 8 * S, c.x + 8 * CS)) + random.randint(-20, 20),
                      GROUND - 80, random.uniform(-0.6, 0.6), -1.0, 30)
            if t > self.length:
                self.go("finale")
        elif ph == "finale":
            hp.eyes = cp.eyes = "happy"
            hp.jump, cp.jump = arc(t / 700, 24), arc(t / 700, 22)
            hp.paws = ((3, 6), (12, 6))
            cp.arms = (True, True)
            if self.every(150):
                spawn("spark", random.randint(30, WIDTH - 30), GROUND - 90, random.uniform(-1, 1), -1.5, 16)
            if t > 1300:
                self.go("home")

    def snack(self, ph, t, hp, cp):
        """A seed drops between them, Messy is faster and shares it."""
        m, c = self.m, self.c
        if ph == "start":  # a seed drops between them
            self.sx = sx = (m.x + 8 * S + c.x + 8 * CS) // 2
            hp.eyes = cp.eyes = "wide"
            self.fx.append(("seed", sx - S, -20 + (GROUND - 12 + 20) * min(1.0, (t / 900) ** 2)))
            if t > 900:
                self.go("rush")
            return
        sx = self.sx
        if ph == "rush":  # the hamster is faster
            self.fx.append(("seed", sx - S, GROUND - 12))
            a = self.move(m, sx - 8 * S, 5)
            self.move(c, sx + 4, 2.4)
            if not a:
                self.running(hp)
            self.walking(cp, 120)
            if a:
                self.go("grab")
        elif ph == "grab":
            hp.seed, hp.paws = True, ((6, 10), (9, 10))
            hp.mouth = 1 + (t // 150) % 2
            hp.look = 0
            cp.eyes = "sad"
            if t > 1400:
                self.go("share")
        elif ph == "share":  # half for Clawd
            hp.eyes, hp.look = "happy", 1
            u = min(1.0, t / 700)
            hx, hy = m.x + 8 * S, BASE_Y + 9 * S
            cx, cy = c.x + 2 * CS, C_BASE_Y + CS
            self.fx.append(("seed", int(hx + (cx - hx) * u), int(hy + (cy - hy) * u) - arc(u, 30)))
            cp.eyes = "wide" if u > 0.5 else "sad"
            if t > 800:
                self.go("munch")
        elif ph == "munch":
            hp.eyes = cp.eyes = "happy"
            hp.mouth = 1 + (t // 150) % 2
            m.puff = max(m.puff, 1.0)
            hp.puff = int(m.puff + 0.5)
            cp.bob = (t // 160) % 2
            cp.arms = (3 + (t // 160) % 2, False)
            if self.every(400):
                spawn("heart", (m.x + c.x) // 2 + 40, BASE_Y, random.uniform(-0.5, 0.5), -1.4, 24)
            if t > 2200:
                self.go("home")

    def leap(self, ph, t, hp, cp):
        """Leapfrog: Messy jumps over Clawd and back, Clawd claps."""
        m, c = self.m, self.c
        if ph == "start":  # make room
            a = self.move(m, 4, 3)
            b = self.move(c, 88, 2.2)
            hp.look = -1 if not a else 1
            if not a:
                self.walking(hp)
            if not b:
                self.walking(cp, 120)
            if a and b:
                self.go("leap1")
                self.leap_from = m.x
        elif ph in ("leap1", "leap2"):
            u = min(1.0, t / 800)
            dest = c.x + 84 if ph == "leap1" else 4
            m.x = int(self.leap_from + (dest - self.leap_from) * u)
            hp.jump = arc(u, 62)
            hp.look = 1 if ph == "leap1" else -1
            hp.paws = ((3, 7), (12, 7))
            cp.eyes = "wide"
            cp.look = -1 if u < 0.5 else 1
            if ph == "leap2":
                cp.look = -cp.look
            if u >= 1.0:
                self.go("land" if ph == "leap1" else "clap")
        elif ph == "land":
            hp.bob = 1 if t < 150 else 0
            hp.eyes, hp.look = "happy", -1
            cp.eyes, cp.look = "wide", 1
            if t > 1100:
                self.leap_from = m.x
                self.go("leap2")
        elif ph == "clap":  # applause
            hp.eyes = cp.eyes = "happy"
            cp.arms = (3 + (t // 120) % 2, 3 + (t // 120) % 2)
            hp.bob = (t // 300) % 2
            if self.every(200):
                spawn("spark", c.x + random.randint(0, 16) * CS, C_BASE_Y - 10, random.uniform(-1, 1), -1.5, 14)
            if t > 1400:
                self.go("home")

    def hide(self, ph, t, hp, cp):
        """Hide and seek: Clawd counts, Messy hides off the edge and peeks,
        Clawd looks around and finds him."""
        m, c = self.m, self.c
        if ph == "start":  # count to ten with the eyes covered
            cp.eyes, cp.arms, cp.look = "closed", (2, 2), 0
            self.fx.append(("count", c.x + 6 * CS, C_BASE_Y - 34, min(10, 1 + t // 450)))
            hp.look = -1
            if not self.move(m, -70, 6):
                self.running(hp)
            if t > 4600:
                self.go("search")
        elif ph == "search":
            cp.look = 1 if t < 1500 else -1
            if t > 1500 and not self.move(c, 96, 1.2):
                self.walking(cp, 140)
            peek = (t // 700) % 3 == 0  # Messy peeks in from the edge now and then
            m.x = -44 if peek else -70
            hp.look, hp.eyes = 1, "wide"
            if t > 4200 and peek:
                self.go("found")
        elif ph == "found":
            self.fx.append(("alert", c.x + 6 * CS, C_BASE_Y - 30))
            cp.eyes, cp.look = "wide", -1
            if not self.move(m, HOME_X, 6):
                self.running(hp)
                hp.look = 1
            else:
                hp.eyes = cp.eyes = "happy"
                hp.jump, cp.jump = arc((t % 700) / 700, 14), arc((t % 700) / 700, 12)
                if self.every(400):
                    spawn("heart", m.x + 10 * S, BASE_Y, random.uniform(-0.5, 0.5), -1.4, 22)
            if t > 3500:
                self.go("home")

    def plane(self, ph, t, hp, cp):
        """Clawd folds a plane; it loops back and lands on Messy's head."""
        m, c = self.m, self.c
        if ph == "start":
            self.meet("fold", hp, cp)
        elif ph == "fold":
            cp.eyes = "down"
            cp.arms = (3 + (t // 220) % 2, 4)
            self.fx.append(("plane", c.x - 16, C_BASE_Y + 16))
            hp.sniff = (t // 150) % 2 == 0
            if t > 1600:
                self.go("fly")
        elif ph == "fly":
            u = min(1.0, t / 3200)
            # One broad loop; its endpoint is exactly the landing position.
            x = (c.x - 16) * (1 - u) + (m.x + 16) * u - 56 * math.sin(2 * math.pi * u)
            y = (C_BASE_Y + 16) * (1 - u) + (BASE_Y - 12) * u - arc(u, 72)
            self.fx.append(("plane", x, y))
            hp.look = 1 if x > m.x + 8 * S else -1
            cp.look = 1 if x > c.x + 8 * CS else -1
            hp.eyes = cp.eyes = "wide"
            cp.arms = (True, False) if t < 500 else (False, False)
            if t > 3200:
                self.go("land")
        elif ph == "land":
            self.fx.append(("plane", m.x + 16, BASE_Y - 12))
            hp.look, hp.eyes = 0, "wide"
            hp.bob = 1 if t < 200 else 0
            cp.eyes = "happy"
            cp.arms = (3 + (t // 180) % 2, 3 + (t // 180) % 2)
            if t > 900:
                hp.eyes, hp.blush = "happy", True
            if t > 2200:
                self.go("home")

    def magic(self, ph, t, hp, cp):
        """A tiny magician's hat produces a suspiciously large seed."""
        m, c = self.m, self.c
        if ph == "start":
            self.meet("spell", hp, cp)
            return
        sx = 116
        if ph in ("spell", "reveal"):
            self.fx.append(("hat", sx, GROUND - 24))
        if ph == "spell":
            cp.arms = ((t // 260) % 2 == 0, False)
            hp.sniff = (t // 180) % 2 == 0
            if t > 900:
                cp.bubble = "ZAUBER!"
            if self.every(280):
                spawn("spark", sx + random.choice((-12, 0, 12)), GROUND - 32, 0, -1, 12)
            if t > 2100:
                self.go("reveal")
        elif ph == "reveal":
            u = min(1.0, t / 900)
            self.fx.append(("bigseed", sx - 8, GROUND - 24 - int(u * 48) // 4 * 4))
            hp.eyes = cp.eyes = "wide"
            cp.arms = (True, True)
            if t > 1500:
                self.go("snatch")
        elif ph == "snatch":
            hp.seed, hp.paws = True, ((6, 10), (9, 10))
            hp.eyes, hp.blush = "happy", True
            hp.mouth = 1 + (t // 160) % 2
            m.puff = max(m.puff, 2.0)
            hp.puff = 2
            cp.eyes = "wide" if t < 900 else "happy"
            if t > 900:
                cp.bubble = "TA-DA!"
            if self.every(500):
                spawn("heart", m.x + 8 * S, BASE_Y - 8, 0, -1, 20)
            if t > 2400:
                self.go("home")

    def mirror(self, ph, t, hp, cp):
        """Messy copies Clawd a beat late, then sneezes: Clawd copies that too."""
        if ph == "start":
            self.meet("copy", hp, cp)
        elif ph == "copy":
            lead = (t // 700) % 4
            echo = (max(0, t - 250) // 700) % 4
            cp.arms = ((True, False), (False, True), (True, True), (False, False))[lead]
            hp.paws = (((3, 5),), ((12, 5),), ((3, 5), (12, 5)), ())[echo]
            cp.jump = 12 if lead == 2 else 0
            hp.jump = 12 if echo == 2 else 0
            hp.eyes = cp.eyes = "happy"
            if t > 5600:
                self.go("sneeze")
        elif ph == "sneeze":
            hp.eyes, hp.sniff = "closed", t < 700
            hp.bob = 1 if 700 <= t < 1100 else 0
            cp.eyes = "wide"
            if 700 <= t < 1300:
                hp.bubble = "HATSCHI!"
            if t > 1400:
                cp.eyes, cp.bob = "closed", 1
                cp.bubble = "HATSCHI!"
            if t > 2300:
                self.go("laugh")
        elif ph == "laugh":
            hp.eyes = cp.eyes = "happy"
            hp.jump = arc((t % 700) / 700, 12)
            cp.jump = arc(((t + 200) % 700) / 700, 12)
            if self.every(450):
                spawn("heart", self.m.x + 12 * S, BASE_Y - 8, 0.3, -1, 20)
            if t > 1800:
                self.go("home")

    def season(self, ph, t, hp, cp):
        """Something for the season: a snowman, kicking leaves, watering a
        flower, ice cream."""
        m, c = self.m, self.c
        if ph == "start":  # stand a little apart, with room in between
            self.sub = seasons.season(seasons.today(self.now))
            a = self.move(m, MEET_X - 26, 2.5)
            b = self.move(c, C_MEET_X + 26, 2.5)
            if not a:
                self.walking(hp)
            if not b:
                self.walking(cp, 120)
            if a and b:
                self.go("act")
            return
        sx = (m.x + 8 * S + c.x + 8 * CS) // 2  # between them
        hp.eyes = cp.eyes = "happy"
        if self.sub == "winter":  # build a snowman
            self.fx.append(("snowman", sx, min(4, t // 1000)))
            if t < 3600:
                hp.paws, cp.arms = ((13, 8), (14, 9)), (3, False)
                hp.bob = cp.bob = (t // 250) % 2
            elif t > 4800:
                hp.jump, cp.jump = arc((t % 700) / 700, 14), arc((t % 700) / 700, 12)
            if t > 6800:
                self.go("home")
        elif self.sub == "autumn":  # kick through the leaves
            i = t // 1500
            a = self.move(m, (16, 70)[i % 2], 4)
            b = self.move(c, (110, 150)[i % 2], 3)
            hp.look = cp.look = 1 if i % 2 else -1
            if not a:
                self.running(hp)
            if not b:
                self.running(cp)
            if self.every(110):
                for x in (m.x + 8 * S, c.x + 8 * CS):
                    spawn("leaf", x + random.randint(-10, 10), GROUND - 4, random.uniform(-1.5, 1.5),
                          random.uniform(-3, -1.5), 60, random.choice(seasons.LEAF_PENS))
            if t > 6000:
                self.go("home")
        elif self.sub == "spring":  # water a flower until it blooms
            self.fx.append(("flower", sx, min(3, t // 1100)))
            hp.look, cp.look = 1, -1
            if t < 4000:
                hp.eyes = "open"
                hp.paws = ((13, 8),)
                hp.props = (("can", 15 * S, 6 * S),)
                if t > 400 and self.every(110):
                    spawn("drop", m.x + 15 * S + 16, BASE_Y + 6 * S + 2, random.uniform(0.6, 1.4), 0.5, 20)
            else:
                hp.jump, cp.jump = arc((t % 700) / 700, 12), arc((t % 700) / 700, 10)
            if t > 5600:
                self.go("home")
        else:  # summer: ice cream
            left = max(0, 3 - t // 1800)
            hp.paws = ((15, 9),)
            hp.props = (("cone", 15 * S, 4 * S, left, 0),)
            cp.arms = (3, False)
            cp.props = (("cone", -8, 2 * CS - 4, left, 1),)
            hp.mouth = 1 + (t // 200) % 2 if left else 0
            if 2500 < t < 4000 and self.every(400):  # Clawd's drips
                spawn("drop", c.x - 4, C_BASE_Y + 2 * CS, 0, 0.5, 20)
            if t > 6000:
                hp.jump, cp.jump = arc((t % 700) / 700, 12), arc((t % 700) / 700, 10)
            if t > 7200:
                self.go("home")

    # effects

    def draw(self, now):
        for f in self.fx:
            kind, fx, fy = f[0], f[1], f[2]
            if kind == "cloud":  # grey dust blob that boils, limbs poking out
                draw_cloud(fx, GROUND - 40, now)
            elif kind == "stars":
                display.set_pen(ALERT_PEN)
                for i in range(3):
                    a = now / 160 + i * 2.09
                    display.rectangle(fx + int(16 * math.cos(a)) - 2, fy + int(5 * math.sin(a)) - 2, 4, 4)
            elif kind == "seed":
                draw_art(SEED_ART, fx, fy, S, SEED_PEN)
            elif kind == "count":  # Clawd counting
                draw_bubble(str(f[3]), int(fx), int(fy))
            elif kind == "snowman":
                draw_snowman(fx, fy)
            elif kind == "flower":
                draw_flower(fx, fy)
            elif kind == "alert":
                draw_alert_sign(int(fx), int(fy))
            elif kind == "plane":
                draw_colour_art(PLANE, TRICK_PENS, fx, fy)
            elif kind == "hat":
                draw_colour_art(MAGIC_HAT, TRICK_PENS, fx - 16, fy)
            elif kind == "bigseed":
                draw_art(SEED_ART, int(fx) // 4 * 4, int(fy) // 4 * 4, 8, SEED_PEN)


# 4 px pixel art: a snowman built ball by ball (w snow, u shade, e coal, o
# carrot) and a flower growing (g stem, l leaf, y bud, p petals)
PLANE = ("wwwwwww", ".wuuuw.", "..wuw..", "..ww...", "..w....")
MAGIC_HAT = (".eeeee.", ".eeeee.", ".eeeee.", ".ppppp.", "eeeeeee")
TRICK_PENS = {"w": pen((255, 241, 232)), "u": pen((194, 195, 199)),
              "e": EYE_PEN, "p": pen((126, 37, 83))}
_BALL = ("..www..", ".wwwwu.", "wwwwwwu", "wwwwwwu", ".wwwuu.")
_MIDDLE = ("..www..", ".wwwwu.", ".wwwwu.", "..wuu..")
SNOWMAN = (("..ww...", ".wwwu..", "..uu..."), _BALL, _MIDDLE + _BALL,
           ("..www..", "..www..", "..wwu..") + _MIDDLE + _BALL,
           ("..www..", "..ewe..", "..wwoo.") + _MIDDLE + _BALL)
SNOW_PENS = {"w": pen((240, 242, 250)), "u": pen((184, 194, 220)), "e": EYE_PEN, "o": pen((255, 140, 0))}
FLOWER = ((".g.", ".g."), (".g.", "lg.", ".gl", ".g."), (".y.", ".g.", "lg.", ".gl", ".g."),
          (".p.", "pyp", ".p.", "lg.", ".gl", ".g."))
FLOWER_PENS = {"g": pen((0, 150, 60)), "l": pen((0, 200, 80)), "y": pen((255, 236, 39)), "p": pen((255, 119, 168))}


def draw_snowman(cx, stage):
    art = SNOWMAN[stage]
    draw_colour_art(art, SNOW_PENS, cx - 14, GROUND + 4 - len(art) * 4)


def draw_flower(cx, stage):
    art = FLOWER[stage]
    draw_colour_art(art, FLOWER_PENS, cx - 6, GROUND + 4 - len(art) * 4)


def draw_cloud(cx, cy, now):
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
        display.set_pen(FUR_PEN if i % 2 else CLAWD_PEN)
        display.rectangle(cx + int(42 * math.cos(a)) - 5, cy + int(30 * math.sin(a)) - 5, 10, 10)
    word = ("POW!", "BAM!", "BONK!")[(now // 600) % 3]
    display.set_pen(ALERT_PEN)
    display.text(word, cx - display.measure_text(word, 2) // 2 + ((now // 600) % 2) * 20 - 10, cy - 58, -1, 2)
