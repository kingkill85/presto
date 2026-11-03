"""Reserve SELECT+START before forwarding either button to a game."""
import time
from gamepad import SELECT, START

CHORD = SELECT | START


class MenuChord:
    def __init__(self):
        self.since = None
        self.pending = 0
        self.locked = False

    def poll(self, held, now):
        keys = held & CHORD
        if self.locked:
            if not keys:
                self.locked = False
            return held & ~CHORD, False
        if keys == CHORD:
            self.locked = True
            self.pending = 0
            self.since = None
            return held & ~CHORD, True
        if keys:
            if self.since is None:
                self.since = now
                self.pending = keys
            if time.ticks_diff(now, self.since) < 120:
                return held & ~CHORD, False
            self.pending = 0
            return held, False
        pulse = self.pending
        self.pending = 0
        self.since = None
        return held | pulse, False
