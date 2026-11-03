"""Debounced room-darkness edge, independent of proximity gestures."""
import time


class Darkness:
    def __init__(self):
        self.dark = None
        self.pending = False
        self.since = None
        self.last_visit = None

    def poll(self, now, sensor, allowed):
        if (not sensor.connected or sensor.lux is None or sensor.light_at is None or
                time.ticks_diff(now, sensor.light_at) > 3000):
            self.dark = None
            self.pending = False
            self.since = None
            return False
        if sensor.near or sensor.proximity > max(120, sensor.baseline + 60):
            self.since = None
            return False  # a covered sensor is not a dark room
        if self.dark is None:
            # Boot/reconnect establishes a baseline, not a darkness event.
            # In the hysteresis band, wait for confirmed light before arming.
            self.dark = sensor.lux < 8
            return False
        crossing = sensor.lux >= 8 if self.dark else sensor.lux <= 3
        if crossing:
            if self.since is None:
                self.since = now
            elif time.ticks_diff(now, self.since) >= 2000:
                self.dark = not self.dark
                self.pending = self.dark
                self.since = None
        else:
            self.since = None
        if self.pending and allowed:
            self.pending = False
            if self.last_visit is None or time.ticks_diff(now, self.last_visit) >= 300000:
                self.last_visit = now
                return True
        return False
