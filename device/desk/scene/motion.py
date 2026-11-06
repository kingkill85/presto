"""Expressive sensor overlays; actor states and world positions stay intact.

A tap on the case: both jump, then look around for whoever knocked. A shake:
they get thrown about, then stagger dizzily with stars round their heads.
Tilting: they lean, flail and slide towards the lower side (up to the screen
edge); level again, they walk back. The slide is only drawn (Pose.dx): their
world positions never change."""
import time
from motion_sensor import TAP, SHAKE

SHAKE_MS = 6000
SHAKEN_MS = 2400  # thrown about; dizzy for the rest
TAP_MS = 5000
WAKE_MS = 6000
SWAY = (0, -1, -2, -1, 0, 1, 2, 1)
STAR_MS = 260  # a new dizzy star per head
SLIDE = 4.5  # px per 66 ms at full tilt
BACK = 1.5  # px per 66 ms walking back
WIDTH = 240
HALF = (32, 40)  # half widths of Messy and Clawd


class MotionReaction:
    def __init__(self, spawn=None):
        self.kind = 0
        self.started = 0
        self.wake_started = None
        self.tilt_started = None
        self.tilting = False
        self.spawn = spawn  # particles.spawn, for the dizzy stars
        self.star_at = 0
        self.slide = 0.0  # px both are slid to the side
        self.slide_at = None

    def update(self, now, event, allowed, tilt=0):
        k = 0 if self.slide_at is None else min(3.0, time.ticks_diff(now, self.slide_at) / 66)
        self.slide_at = now
        if allowed and abs(tilt) > 0.2:
            self.slide = max(-WIDTH, min(WIDTH, self.slide + tilt * SLIDE * k))
        elif self.slide:
            step = BACK * k
            self.slide = 0.0 if abs(self.slide) <= step else self.slide - step * (1 if self.slide > 0 else -1)
        if not allowed:
            self.kind = 0
            self.wake_started = self.tilt_started = None
            self.tilting = False
            return
        if event == TAP and abs(tilt) > 0.15:
            event = 0  # tilting the case jolts the tap detector: the tilt wins
            self.wake_started = now  # but a knock still wakes sleepers
        if event:
            self.kind, self.started = event, now
            self.wake_started = now
        elif self.kind and time.ticks_diff(now, self.started) >= (SHAKE_MS if self.kind == SHAKE else TAP_MS):
            self.kind = 0

        if abs(tilt) < 0.15:
            self.tilting = False
            self.tilt_started = None
        elif abs(tilt) > 0.25 and not self.tilting:
            self.tilting = True
            if self.kind == TAP:  # that "tap" was the case being tipped
                self.kind = 0
            self.tilt_started = self.wake_started = now

    def waking(self, now):
        return (self.wake_started is not None
                and time.ticks_diff(now, self.wake_started) < WAKE_MS)

    def apply(self, now, tilt, hp, cp, sleeping=(False, False), heads=None):
        """heads: ((x, y), (x, y)) above Messy and Clawd, for the dizzy stars."""
        stars = (self.kind == SHAKE and self.spawn and heads
                 and time.ticks_diff(now, self.started) >= SHAKEN_MS - 400
                 and time.ticks_diff(now, self.star_at) >= STAR_MS)
        if stars:
            self.star_at = now
        for i, (p, clawd, asleep) in enumerate(((hp, False, sleeping[0]), (cp, True, sleeping[1]))):
            shift = 0
            if self.slide and heads:  # slid, but never off the screen
                cx = heads[i][0]
                shift = int(max(HALF[clawd] - cx, min(WIDTH - HALF[clawd] - cx, self.slide)))
            if asleep:
                p.dx = getattr(p, 'dx', 0) + shift
                if not self.waking(now):
                    continue
                self._wake(now, p, clawd)
            shown = self._apply(now, tilt, p, clawd)
            if shift and not asleep:
                if not shown:  # level again: walk back
                    p.look = -1 if shift > 0 else 1
                    p.step = 1 + (now // 140) % 2 if (now // 140) % 4 < 2 else 0
                p.dx = getattr(p, 'dx', 0) + shift
            if shown and stars:
                x, y = heads[i]
                a = (now // STAR_MS) % 4
                self.spawn("spark", x + (-14, 6, 14, -6)[a], y - 10 - (a % 2) * 4,
                           (0.8, 0.8, -0.8, -0.8)[a], -0.3, 8)

    def _wake(self, now, p, clawd):
        elapsed = time.ticks_diff(now, self.wake_started)
        p.eyes = 'open'
        p.bob = 0
        p.look = (0, -1, 0, 1, 0, -1)[min(5, elapsed // 1000)]
        if elapsed >= WAKE_MS - 1000:
            # A slow yawn before the original sleep pose resumes.
            p.eyes = 'closed' if elapsed % 650 < 280 else 'open'
            if clawd:
                p.arms = (True, False)
            else:
                p.mouth = 3
                p.paws = ((3, 9), (12, 9))
        elif clawd:
            p.think = 1 + (elapsed // 700) % 2
        else:
            p.ear = (elapsed // 250) % 2 == 0

    def _apply(self, now, tilt, p, clawd):
        """True while a reaction shows on this actor."""
        if not self.kind and abs(tilt) <= 0.2:
            return False
        p.hide = False
        p.sink = 0
        p.eyes = 'open'
        p.bob = 0
        elapsed = time.ticks_diff(now, self.started)
        if self.kind == SHAKE and elapsed < SHAKEN_MS:  # thrown about
            phase = elapsed // 120
            amplitude = 10 if elapsed < 1600 else 6
            dx = SWAY[phase % 8] * amplitude
            p.dx = -dx if clawd else dx
            p.step = (2 if clawd else 1) if phase % 2 else (1 if clawd else 2)
            p.jump = max(getattr(p, 'jump', 0), (0, 6, 12, 6)[phase % 4])
            p.look = -1 if dx > 0 else 1 if dx < 0 else 0
            p.eyes = 'wide'
            p.bubble = '!'
            if clawd:
                p.arms = (phase % 2 == 0, phase % 2 == 1)
            else:
                p.paws = ((-1, 4), (16, 5)) if phase % 2 else ((-1, 5), (16, 4))
                p.mouth = 3
        elif self.kind == SHAKE:  # dizzy: stagger, eyes shut, stars
            t = elapsed - SHAKEN_MS
            p.dx = SWAY[(t // 260) % 8] * (3 if t < 2400 else 1)
            p.eyes = 'closed' if (t // 500) % 3 else 'open'
            p.bob = (t // 520) % 2
            p.look = (-1, 0, 1, 0)[(t // 520) % 4]
            if t > 2600:
                p.bubble = '?'
        elif self.kind == TAP and abs(tilt) <= 0.25:
            if elapsed < 700:  # startled
                p.eyes = 'wide'
                p.look = 0
                p.jump = max(getattr(p, 'jump', 0), int(16 * max(0, 1 - abs(elapsed - 300) / 300)))
                p.bubble = '!'
                if clawd:
                    p.arms = (True, True)
                else:
                    p.paws = ((-1, 4), (16, 4))
                return True
            p.look = (-1, -1, 1, 1, 0, 0, 0, 0, 0)[min(8, (elapsed - 700) // 500)]
            if elapsed < 3600:  # who knocked? searching
                p.bubble = '?'
                if clawd:
                    p.think = 1 + (elapsed // 500) % 3
                    p.arms = ((elapsed // 400) % 2 == 0, False)
                else:
                    p.ear = (elapsed // 180) % 2 == 0
                    p.sniff = (elapsed // 150) % 2 == 0
                    p.paws = ((-1, 5),)  # paw to the ear, listening
            else:  # a shrug at you
                p.eyes = 'happy'
                if clawd:
                    p.arms = (True, True) if elapsed < 4400 else (False, False)
                else:
                    p.paws = ((-1, 5), (16, 5)) if elapsed < 4400 else ()
            return True
        else:  # tilted: lean and flail for balance
            direction = 1 if tilt > 0 else -1
            steep = abs(tilt) > 0.65
            t = time.ticks_diff(now, self.tilt_started) if self.tilt_started is not None else 0
            sway = SWAY[(t // 180) % 8]
            p.dx = direction * (8 if steep else 4) + sway * 2
            p.look = -direction
            p.step = (1 if direction > 0 else 2) if (t // 180) % 2 else (2 if direction > 0 else 1)
            p.eyes = 'wide' if steep else 'open'
            if steep:
                p.bubble = '!'
            flap = (t // 160) % 2
            if clawd:
                p.arms = (bool(flap), not flap)
            else:
                p.paws = ((-1, 4), (16, 5)) if flap else ((-1, 5), (16, 4))
            return True
        return True
