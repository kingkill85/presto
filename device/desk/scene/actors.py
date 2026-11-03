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

from desk import sound
from desk.scene import seasons, sprites
from desk.scene.particles import spawn
from desk.scene.scene import WHEEL_CX, WHEEL_CY
from desk.scene.sprites import BASE_Y, C_BASE_Y, C_HOME_X, CS, GROUND, HOME_X, S

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
        self.bubble = None  # "name", "tick", "!" or any text above the head
        self.dx = 0  # drawn this many px to the side (shaking)
        self.props = ()  # things held: (kind, x, y, ...) in px from the actor's corner
        # Messy
        self.paws = ()  # (col, row) of raised paws
        self.mouth = 0
        self.blush = self.seed = self.ear = self.sniff = False
        self.puff = 0  # cheeks stuffed, 0..2
        self.seed_y = None  # a seed falling down to it
        self.hole = 0  # a hole dug in the ground, 0..1 of its size
        self.sink = 0  # px down into that hole
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
        "sad": (1600, 1600), "dig": (5600, 5600), "stretch": (3600, 3600), "sneeze": (1900, 1900),
        "ball": LONG, "event": LONG, "wheel": LONG, "broken": LONG, "duo": LONG,
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
        if self.state == "sleep":
            return "stretch"  # always after waking up
        r = random.random()
        if r < 0.10 and other in FREE:
            return "ball"
        if r < 0.24 and other in FREE:
            return "duo"
        if r < 0.36:
            return "idle"
        if r < 0.48:
            return "look"
        if r < 0.64:
            return "walk"
        if r < 0.74:
            return "eat"
        if r < 0.82:
            return "wash"
        if r < 0.89:
            return "dig"
        if r < 0.92:
            return "sneeze"
        return "sleep"

    def act(self, now, k, p, awake=False):
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
            if awake:
                return  # brief sensor wake-up; keep sleep state and timer
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
        elif state == "dig":
            self.dig(t, p)
        elif state == "stretch":
            self.stretch(t, p)
        elif state == "sneeze":
            self.sneeze(t, k, p)
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

    def dig(self, t, p):
        """Dig a hole, vanish halfway into it, come up with a seed."""
        cx = self.x + 8 * S
        if t < 2600:  # scrabble, dirt flies
            a = (t // 120) % 2
            p.paws = ((5, 11 + a), (10, 12 - a))
            p.bob = a
            p.hole = t / 2600
            if self.every(t, 140):
                spawn("dirt", cx + random.randint(-8, 8), GROUND - 2, random.choice((-1, 1)) * random.uniform(1, 2.5),
                      random.uniform(-3.5, -2), 30, seasons.soil_pen())
            return
        p.hole = 1
        if t < 3800:  # down into it
            p.eyes = "closed"
            p.sink = int(min(1, (t - 2600) / 500) * 7) * 4
        elif t < 4500:  # up again with a seed
            u = (t - 3800) / 700
            p.sink = int(max(0.0, 1 - u * 2) * 7) * 4
            p.jump = 0 if p.sink else int(10 * math.sin(math.pi * u))
            p.eyes, p.seed, p.paws = "happy", True, ((6, 10), (9, 10))
        else:  # proud of it
            p.eyes, p.blush, p.seed, p.paws = "happy", True, True, ((6, 10), (9, 10))
            p.mouth = 1 + (t // 150) % 2

    def stretch(self, t, p):
        """After waking up: yawn, stretch up high, shake the fur."""
        if t < 900:  # yawn
            p.eyes, p.mouth, p.paws = "closed", 2, ((3, 9), (12, 9))
        elif t < 2000:  # up on tiptoes, paws up high
            p.eyes, p.jump, p.paws, p.blush = "closed", 6, ((-1, 4), (-1, 5), (16, 4), (16, 5)), True
        elif t < 3100:  # shake
            p.look = 1 if (t // 70) % 2 else -1
            p.ear = (t // 140) % 2 == 0
            p.eyes = "closed"
            if self.every(t, 110):
                spawn("fluff", self.x + random.randint(0, 16) * S, BASE_Y + random.randint(2, 10) * S,
                      random.uniform(-1.2, 1.2), random.uniform(-1.2, -0.3), 18)
        else:
            p.eyes = "happy"

    def sneeze(self, t, k, p):
        """Ah... ah... HATSCHI! and it blows him back."""
        if t < 800:
            p.eyes, p.sniff = "closed", True
            p.jump = int(t / 800 * 6)
        elif t < 1300:
            if t < 1100:
                p.bubble = "HATSCHI!"
            p.eyes, p.bob = "wide", 1
            self.x = max(self.MIN_X, self.x - 3 * k)
            if t < 950 and self.every(t, 40):
                spawn("drop", self.x + 9 * S, BASE_Y + 8 * S, random.uniform(1, 3), random.uniform(-2, -0.5), 12)
        else:
            p.eyes, p.bob = "closed", 1

    def finish(self, now, p):
        self.blink(now, p, 1800, 5000)


class Clawd(Actor):
    DURATIONS = {
        "idle": (2000, 5000), "look": (2000, 3000), "walk": (6000, 6000), "wave": (1800, 1800),
        "think": (3000, 5000), "sleep": (10000, 18000), "happy": (1400, 1400), "sad": (1600, 1600),
        "coffee": (6200, 6200), "juggle": (6400, 6400),
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
        if r < 0.34:
            return "idle"
        if r < 0.50:
            return "look"
        if r < 0.64:
            return "walk"
        if r < 0.72:
            return "wave"
        if r < 0.80:
            return "think"
        if r < 0.87:
            return "coffee"
        if r < 0.94:
            return "juggle"
        return "sleep"

    def act(self, now, k, p, awake=False):
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
            if awake:
                return  # brief sensor wake-up; keep sleep state and timer
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
        elif state == "coffee":
            self.coffee(t, p)
        elif state == "juggle":
            self.juggle(t, p)
        elif state == "done":
            p.eyes = "happy"
            if t < 1400:  # two hops, then stand proud
                p.jump = int(20 * math.sin(math.pi * ((t % 700) / 700)))
                p.arms = (True, True)
            else:
                p.bob = (t // 1000) % 2
            p.bubble = "tick"

    def coffee(self, t, p):
        """A cup of coffee: blow on it, sip, then a little too much energy."""
        if t < 700:  # lift the cup
            row = 4 if t < 350 else 3
            p.arms = (False, row)
            p.props = (("mug", 16 * CS, row * CS - 2),)
        elif t < 2800:  # blow on it
            p.arms, p.look = (False, 3), 1
            p.props = (("mug", 16 * CS, 3 * CS - 2),)
            if self.every(t, 300):
                spawn("steam", self.x + 16 * CS + 2, C_BASE_Y + 2 * CS, 0, -0.6, 20)
        elif t < 4200:  # sip
            p.arms, p.eyes = (False, 2), "closed"
            p.props = (("mug", 13 * CS, 2 * CS - 2),)
        else:  # buzzing
            p.eyes = "wide"
            p.dx = 2 if (t // 50) % 2 else -2
            p.arms = ((t // 100) % 2 == 0, (t // 100) % 2 == 1)

    def juggle(self, t, p):
        """Juggle three blocks; at the end one falls on his head."""
        cx = 8 * CS - 2
        if t < 5000:
            hand = (t // 300) % 2
            p.arms = (hand == 0, hand == 1)
            props = []
            for i in range(3):  # each block goes round the loop, a third apart
                a = 2 * math.pi * ((t / 900 + i / 3) % 1)
                props.append(("block", cx + int(34 * math.cos(a)), -22 - int(18 * math.sin(a)), i))
            p.props = props
        elif t < 5600:  # missed one, and it comes down on his head
            u = (t - 5000) / 600
            p.props = (("block", cx, int(-60 + 55 * u * u), 0),)
            p.eyes = "wide"
        else:
            if self.every(t, 10000):  # bonk
                for _ in range(4):
                    spawn("spark", self.x + 8 * CS, C_BASE_Y - 4, random.uniform(-2, 2),
                          random.uniform(-2, -0.5), 10)
            p.eyes, p.bob = "closed", 1
            p.props = (("block", 16 * CS + 2, 10 * CS - 5, 0),)  # on the ground next to him

    def finish(self, now, p):
        self.blink(now, p, 2000, 6000)
