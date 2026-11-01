# Messy and Clawd: each runs a little state machine. A state lasts a random
# time, then the actor picks the next one. While a director (ball game, scene
# for two, pirate visit) runs, both are in its state ("ball", "duo", "event")
# and the director moves and poses them instead.
#
# Movement is time based: k is the frame time in units of 66 ms, and all speeds
# are per 66 ms.

import math
import random
import time

from messy import sound, sprites
from messy.scene import WHEEL_CX, WHEEL_CY, spawn
from messy.sprites import BASE_Y, C_BASE_Y, C_HOME_X, CS, HOME_X, S

# Walk and run cycles: (foot lifted, hop in screen pixels)
WALK = ((1, 3), (0, 0), (2, 3), (0, 0))
RUN = ((1, 7), (0, 1), (2, 7), (0, 1))
FREE = ("idle", "look", "walk", "wash", "wave", "think")  # may be pulled into a ball game or a scene
DIRECTED = ("ball", "duo", "event")  # a director is in charge
LONG = (600000, 600000)  # until something else ends it


class Pose:
    """How an actor looks in this frame. Reset every frame, then filled in by
    the actor's state and by a director."""

    def reset(self):
        self.eyes = "open"
        self.look = 0  # -1 left, 1 right
        self.step = 0  # which foot is lifted
        self.bob = 0  # squashed down by one pixel
        self.jump = 0  # screen pixels up
        self.hide = False
        self.umbrella = False
        self.bubble = None  # "name", "tick", "!" above the head
        # Messy
        self.paws = ()  # (col, row) of raised paws
        self.mouth = 0
        self.blush = self.seed = self.ear = self.sniff = False
        self.puff = 0  # cheeks stuffed, 0..2
        self.seed_y = None  # a seed falling down to it
        # Clawd
        self.arms = (False, False)  # per side: True up, False down or a row
        self.laptop = False
        self.think = 0  # thinking dots


class Actor:
    DURATIONS = {}  # state -> (min ms, max ms)
    MIN_X = MAX_X = 0
    MIN_WALK = 10  # px, shortest walk
    WALK_SPEED = 2.0  # px per 66 ms
    STEP_MS = 110  # walk cycle step

    def __init__(self, x, duration, blink_in):
        now = time.ticks_ms()
        self.x = self.target = x
        self.state = "idle"
        self.t0 = now
        self.duration = duration
        self.last_spawn = 0
        self.next_blink = time.ticks_add(now, blink_in)
        self.pose = Pose()

    def start(self, name):
        self.state = name
        self.t0 = time.ticks_ms()
        self.last_spawn = -100000
        lo, hi = self.DURATIONS[name]
        self.duration = random.randint(lo, hi)
        if name == "walk":
            while abs(self.target - self.x) < self.MIN_WALK:
                self.target = random.randint(self.MIN_X, self.MAX_X)

    def elapsed(self, now):
        return time.ticks_diff(now, self.t0)

    def timed_out(self, now):
        return self.elapsed(now) > self.duration

    def every(self, t, ms):
        """True once every ms milliseconds of the current state."""
        if t - self.last_spawn >= ms:
            self.last_spawn = t
            return True
        return False

    def walk(self, t, k, p):
        """Walk to the target, then stand still for a moment. False once there."""
        if self.x == self.target:
            return False
        d = 1 if self.target > self.x else -1
        p.look = d
        self.x += d * self.WALK_SPEED * k
        if (d > 0 and self.x >= self.target) or (d < 0 and self.x <= self.target):
            self.x = self.target
            self.duration = t + 500  # then pick something new
        p.step, p.jump = WALK[(t // self.STEP_MS) % 4]
        return True

    def hop(self, t, p, height):
        """Happy hops, squashed on the ground between them."""
        phase = (t % 700) / 700
        if phase < 0.12 or phase > 0.9:
            p.bob = 1
        else:
            p.jump = int(height * math.sin(math.pi * (phase - 0.12) / 0.78))

    def blink(self, now, p, lo, hi):
        """Blink now and then while the eyes are open."""
        if p.eyes == "open" and time.ticks_diff(now, self.next_blink) > 0:
            p.eyes = "closed"
            if time.ticks_diff(now, self.next_blink) > 140:
                self.next_blink = time.ticks_add(now, random.randint(lo, hi))


class Messy(Actor):
    DURATIONS = {
        "idle": (2000, 4500), "look": (2000, 2000), "walk": (9000, 9000), "eat": (6000, 6000),
        "wash": (2600, 2600), "sleep": (12000, 22000), "happy": (1400, 1400), "startle": (900, 900),
        "sad": (1600, 1600), "ball": LONG, "event": LONG, "wheel": LONG, "broken": LONG, "duo": LONG,
    }
    MIN_X, MAX_X = sprites.MIN_X, sprites.MAX_X
    MIN_WALK = 12
    WALK_SPEED = 2.5
    STATE_SOUNDS = {"happy": "squeak", "startle": "startle", "eat": "whistle", "sleep": "yawn"}
    WHEEL_CYCLE_MS = 12000  # in the wheel every 12 s ...
    WHEEL_JOG_MS = 3500     # ... a 3.5 s jog, the rest of the time it rests

    def __init__(self):
        super().__init__(HOME_X, 3000, 2500)
        self.puff = 0.0  # stuffed cheeks, go back slowly
        self.wheel_turn = 0.0
        self.eat_sound = 0
        self.last_munch = 0

    def start(self, name):
        super().start(name)
        self.eat_sound = 0
        self.last_munch = 0
        if name in self.STATE_SOUNDS:
            sound.play(self.STATE_SOUNDS[name])

    def pick(self, other):
        """The next state; "ball" or "duo" ask for a director."""
        r = random.random()
        if r < 0.10 and other in FREE:
            return "ball"
        if r < 0.24 and other in FREE:
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

    def act(self, now, k, p):
        """Pose for this frame in its own states (not the directed ones)."""
        t = self.elapsed(now)
        state = self.state
        x = self.x
        if state == "idle":
            p.bob = (t // 1100) % 2
            p.sniff = t % 2600 < 300 and (t // 75) % 2 == 0
            p.ear = t % 3700 < 160
        elif state == "look":
            p.look = (-1, 0, 1, 0)[(t // 500) % 4]
        elif state == "walk":
            if not self.walk(t, k, p):
                p.sniff = (t // 75) % 2 == 0
        elif state == "eat":
            self.eat(t, p)
        elif state == "wash":
            p.eyes = "closed"
            up = (t // 250) % 2
            p.paws = ((3, 7 + up), (12, 8 - up))
        elif state == "sleep":
            p.eyes = "closed"
            p.bob = (t // 1500) % 2
            if self.every(t, 1300):
                if t > 2000:
                    sound.play("snore", 0.03)
                spawn("zed", x + 13 * S, BASE_Y + S, 0.4, -0.7, 45)
        elif state == "happy":
            p.eyes = "happy"
            p.blush = True
            self.hop(t, p, 28)
            if self.every(t, 350):
                spawn("heart", x + random.randint(0, 12) * S, BASE_Y, random.uniform(-0.5, 0.5), -1.6, 22)
        elif state == "startle":
            p.eyes = "wide"
            p.jump = int(18 * math.sin(math.pi * min(1, t / 400)))
            if 400 < t < 520:
                p.bob = 1
        elif state == "sad":
            p.eyes = "closed"
            p.bob = 1
        elif state == "wheel":  # pipeline running: a calm jog now and then, mostly resting
            if t % self.WHEEL_CYCLE_MS < self.WHEEL_JOG_MS:
                p.look = 1
                p.step, jump = WALK[(t // 140) % 4]
                p.jump = jump // 2
                self.wheel_turn += 0.035 * k
            else:
                p.bob = (t // 1300) % 2
                p.sniff = t % 2600 < 300 and (t // 75) % 2 == 0
                p.look = (0, 0, 1, 0, -1)[(t // 1700) % 5]
        elif state == "broken":  # pipeline failed: sits in the stopped wheel
            p.eyes = "closed" if (t // 2500) % 3 else "open"
            p.bob = 1
            if self.every(t, 900):  # smoke from the hub
                spawn("smoke", WHEEL_CX - 4 + random.randint(-6, 6), WHEEL_CY - 6, random.uniform(-0.3, 0.3), -0.8, 30)
        # stuffed cheeks slowly go back to normal
        if state != "eat":
            self.puff = max(0.0, self.puff - 0.012 * k)
        p.puff = int(self.puff + 0.5)

    def eat(self, t, p):
        if t < 900:  # a seed drops from above
            p.eyes = "wide"
            p.seed_y = -30 + (BASE_Y + 9 * S + 30) * (t / 900) ** 2
        elif t < 5000:  # munch munch, cheeks fill up
            p.seed = t < 4200
            if self.eat_sound == 0:
                sound.play("catch")
                self.eat_sound = 1
            elif p.seed and t - self.last_munch >= 300:
                sound.play("munch", 0.15)
                self.last_munch = t
            p.paws = ((6, 10), (9, 10))
            p.mouth = 1 + (t // 150) % 2
            p.eyes = "closed" if (t // 900) % 3 == 2 else "open"
            self.puff = max(self.puff, min(2.0, (t - 900) / 1500))
            if p.seed and self.every(t, 350):
                spawn("crumb", self.x + 8 * S, BASE_Y + 10 * S, random.uniform(-1.5, 1.5), -1.0, 25)
        else:
            p.eyes = "happy"
            p.blush = True
            if self.eat_sound == 1:
                sound.play("yum")
                self.eat_sound = 2

    def finish(self, now, p):
        self.blink(now, p, 1800, 5000)


class Clawd(Actor):
    DURATIONS = {
        "idle": (2000, 5000), "look": (2000, 3000), "walk": (6000, 6000), "wave": (1800, 1800),
        "think": (3000, 5000), "sleep": (10000, 18000), "happy": (1400, 1400), "sad": (1600, 1600),
        "ball": LONG, "event": LONG, "work": LONG, "alert": LONG, "done": LONG, "duo": LONG,
    }
    MIN_X, MAX_X = sprites.C_MIN_X, sprites.C_MAX_X
    MIN_WALK = 10
    WALK_SPEED = 1.6
    STEP_MS = 120

    def __init__(self):
        super().__init__(C_HOME_X, 2000, 1500)
        self.flash_until = 0  # holds up a tick: one agent done, others still work

    def pick(self, other):
        r = random.random()
        if r < 0.06 and other in FREE:
            return "ball"
        if r < 0.16 and other in FREE:
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

    def act(self, now, k, p):
        t = self.elapsed(now)
        state = self.state
        if state == "idle":
            p.bob = (t // 900) % 2
        elif state == "look":
            p.look = (-1, -1, 0, 1)[(t // 600) % 4]  # mostly at the hamster
        elif state == "walk":
            self.walk(t, k, p)
        elif state == "wave":
            p.eyes = "happy"
            p.look = -1
            p.arms = ((t // 250) % 2 == 0, False)
        elif state == "think":
            p.look = 1
            p.think = 1 + (t // 400) % 4
        elif state == "sleep":
            p.eyes = "closed"
            p.bob = (t // 1600) % 2
            if self.every(t, 1500):
                spawn("zed", self.x + 13 * CS, C_BASE_Y - 6, 0.4, -0.7, 45)
        elif state == "happy":
            p.eyes = "happy"
            p.arms = (True, True)
            self.hop(t, p, 24)
            if self.every(t, 300):
                spawn("spark", self.x + random.randint(0, 14) * CS, C_BASE_Y, random.uniform(-0.6, 0.6), -1.6, 20)
        elif state == "sad":
            p.eyes = "sad"
            p.bob = 1
        elif state == "work":  # an agent is working: typing away on a laptop
            p.laptop = True
            p.eyes = "down"
            tap = (t // 110) % 4
            p.arms = (5 if tap == 0 else 4, 5 if tap == 2 else 4)
            p.bob = 1 if (t // 2200) % 4 == 3 else 0
            if time.ticks_diff(self.flash_until, now) > 0:
                p.eyes, p.look, p.bob = "happy", 0, 0
                p.arms = (True, 4)
                p.bubble = "tick"
            elif (t // 2600) % 3 == 2:
                p.eyes, p.look = "open", 1  # glance up and think
                p.think = 1 + (t // 400) % 4
        elif state == "alert":  # an agent waits for an answer: wave and jump
            p.eyes = "wide" if (t // 1200) % 2 else "open"
            p.look = -1
            p.arms = ((t // 180) % 2 == 0, False)
            p.jump = int(6 * abs(math.sin(t * math.pi / 500)))
            p.bubble = "!"
        elif state == "done":
            p.eyes = "happy"
            if t < 1400:  # two hops, then stand proud
                p.jump = int(20 * math.sin(math.pi * ((t % 700) / 700)))
                p.arms = (True, True)
            else:
                p.bob = (t // 1000) % 2
            p.bubble = "tick"

    def finish(self, now, p):
        self.blink(now, p, 2000, 6000)
