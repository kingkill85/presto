"""Expressive sensor overlays; actor states and world positions stay intact."""
import time
from motion_sensor import TAP, SHAKE

SHAKE_MS = 3000
TAP_MS = 3500
WAKE_MS = 6000
SWAY = (0, -1, -2, -1, 0, 1, 2, 1)


class MotionReaction:
    def __init__(self):
        self.kind = 0
        self.started = 0
        self.wake_started = None
        self.tilt_started = None
        self.tilting = False

    def update(self, now, event, allowed, tilt=0):
        if not allowed:
            self.kind = 0
            self.wake_started = self.tilt_started = None
            self.tilting = False
            return
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
            self.tilt_started = self.wake_started = now

    def waking(self, now):
        return (self.wake_started is not None
                and time.ticks_diff(now, self.wake_started) < WAKE_MS)

    def apply(self, now, tilt, hp, cp, sleeping=(False, False)):
        for p, clawd, asleep in ((hp, False, sleeping[0]), (cp, True, sleeping[1])):
            if asleep:
                if not self.waking(now):
                    continue
                self._wake(now, p, clawd)
            self._apply(now, tilt, p, clawd)

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
                p.mouth = 1
                p.paws = ((3, 7),)
        elif clawd:
            p.think = 1 + (elapsed // 700) % 2
        else:
            p.ear = (elapsed // 250) % 2 == 0

    def _apply(self, now, tilt, p, clawd):
        if not self.kind and abs(tilt) <= 0.2:
            return
        p.hide = False
        p.sink = 0
        p.eyes = 'open'
        p.bob = 0
        if self.kind == SHAKE:
            elapsed = time.ticks_diff(now, self.started)
            phase = elapsed // 150
            amplitude = 8 if elapsed < 1500 else 4 if elapsed < 2400 else 0
            dx = SWAY[phase % 8] * amplitude
            p.dx = -dx if clawd else dx
            p.step = (2 if clawd else 1) if phase % 2 else (1 if clawd else 2)
            p.jump = max(getattr(p, 'jump', 0), (0, 4, 8, 4)[phase % 4] if elapsed < 1800 else 0)
            p.look = -1 if dx > 0 else 1 if dx < 0 else 0
            p.bubble = '!' if elapsed < 1800 else '?'
        elif self.kind == TAP:
            elapsed = time.ticks_diff(now, self.started)
            p.look = (0, -1, -1, 1, 1, 0, 0)[min(6, elapsed // 500)]
            if elapsed < 400:
                p.jump = max(getattr(p, 'jump', 0), 4 if elapsed < 250 else 0)
            if clawd:
                p.think = 1 + (elapsed // 600) % 3
                p.arms = (elapsed < 800, False)
            else:
                p.ear = (elapsed // 180) % 2 == 0
                p.paws = ((3, 7),) if elapsed < 1000 else ()
            return
        else:
            direction = 1 if tilt > 0 else -1
            elapsed = time.ticks_diff(now, self.tilt_started) if self.tilt_started is not None else 0
            sway = SWAY[(elapsed // 220) % 8]
            p.dx = direction * (12 if abs(tilt) > 0.65 else 8) + sway * 2
            p.look = -direction
            p.step = (1 if direction > 0 else 2) if (elapsed // 220) % 2 else (2 if direction > 0 else 1)
            p.bob = (elapsed // 440) % 2
        if clawd:
            p.arms = (True, True)
        else:
            p.paws = ((1, 7), (13, 7))
