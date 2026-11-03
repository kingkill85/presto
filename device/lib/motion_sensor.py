"""Optional LSM6DS3TR-C: bounded polling, startup calibration and gestures.
Register reference: https://github.com/pimoroni/lsm6ds3-micropython
Accelerometer +/-2 g, gyro +/-250 dps; no interrupt pin required.
"""
import time
from machine import I2C, Pin

TAP, SHAKE = 1, 2


class MotionSensor:
    def __init__(self, bus=None):
        self.bus = bus
        self.connected = False
        self.ready = False
        self.address = 0x6a
        self.next_poll = time.ticks_ms()
        self.sample_at = None
        self.buf = bytearray(12)
        self.base = [0.0, 0.0, 0.0]
        self.accel = [0.0, 0.0, 0.0]
        self.gyro = [0.0, 0.0, 0.0]
        self.samples = 0
        self.tilt = 0.0
        self.last_event = None
        self.shock_at = None

    def _clear(self):
        self.ready = False
        self.samples = 0
        self.tilt = 0.0
        self.shock_at = None
        self.sample_at = None
        self.last_event = None

    def poll(self, now):
        if time.ticks_diff(now, self.next_poll) < 0:
            return 0
        self.next_poll = time.ticks_add(now, 30)
        try:
            if self.bus is None:
                self.bus = I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)
            if not self.connected:
                for address in (0x6a, 0x6b):
                    try:
                        identity = self.bus.readfrom_mem(address, 0x0f, 1)[0]
                    except OSError:
                        continue
                    if identity == 0x6a:
                        self.address = address
                        break
                else:
                    raise OSError('No LSM6DS3TR-C')
                # BDU + auto-increment, 416 Hz accel for tap detection, 104 Hz gyro.
                # Latch taps on all axes; single tap, threshold 9/32 full scale.
                for reg, value in ((0x12, 0x44), (0x10, 0x60), (0x11, 0x40),
                                   (0x58, 0x8f), (0x59, 9), (0x5a, 6),
                                   (0x5b, 0), (0x5e, 0x40)):
                    self.bus.writeto_mem(self.address, reg, bytes((value,)))
                self.connected = True
                self._clear()
                self.next_poll = time.ticks_add(now, 100)
                return 0
            status = self.bus.readfrom_mem(self.address, 0x1e, 1)[0]
            if status & 3 != 3:
                if self.sample_at is not None and time.ticks_diff(now, self.sample_at) > 1000:
                    raise OSError('Stale motion data')
                # Bound the wait for a first sample too.
                if self.sample_at is None:
                    self.sample_at = now
                return 0
            self.bus.readfrom_mem_into(self.address, 0x22, self.buf)
            tap = self.bus.readfrom_mem(self.address, 0x1c, 1)[0] & 0x20
            for i in range(6):
                raw = self.buf[2*i] | self.buf[2*i+1] << 8
                if raw & 0x8000:
                    raw -= 65536
                if i < 3:
                    self.gyro[i] = raw * 0.00875
                else:
                    self.accel[i-3] = raw * 0.000061
            self.sample_at = now
            strength = sum(v*v for v in self.accel)
            spin = max(abs(v) for v in self.gyro)
            if not self.ready:
                if not 0.7 < strength < 1.3 or spin > 20:
                    self.samples = 0
                    return 0
                if self.samples and max(abs(self.accel[i]-self.base[i]) for i in range(3)) > 0.12:
                    self.samples = 0
                self.samples += 1
                for i in range(3):
                    self.base[i] += (self.accel[i]-self.base[i]) / self.samples
                self.ready = self.samples >= 30
                return 0
            # Dominant gravity change supports a stick mounted flat or upright.
            delta = max((self.accel[i]-self.base[i] for i in range(3)), key=abs)
            target = max(-1.0, min(1.0, delta / 0.65)) if abs(delta) > 0.15 else 0.0
            self.tilt += (target-self.tilt) * 0.18
            shock = strength > 2.7 or spin > 140
            event = 0
            if shock:
                if self.shock_at is not None and time.ticks_diff(now, self.shock_at) < 400:
                    event = SHAKE
                    self.shock_at = None
                else:
                    self.shock_at = now
            elif tap:
                event = TAP
            if event and (self.last_event is None or time.ticks_diff(now, self.last_event) >= 2000):
                self.last_event = now
                return event
            return 0
        except OSError:
            self.connected = False
            self._clear()
            self.next_poll = time.ticks_add(now, 2000)
            return 0
