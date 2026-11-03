"""Optional LTR559 on the Multi-Sensor Stick; bounded I2C, no sleep or scans.
Register map/lux coefficients: Pimoroni's ltr559 driver (MIT).
https://github.com/pimoroni/pimoroni-pico/tree/main/drivers/ltr559
"""
import time
from machine import I2C, Pin

HELLO, COVER, REVEAL = 1, 2, 3

class AmbientSensor:
    def __init__(self, bus=None):
        self.bus = bus
        self.connected = False
        self.next_poll = time.ticks_ms()
        self.light_at = None
        self.lux = None
        self.proximity = 0
        self.baseline = 60.0
        self.near = False
        self.near_count = 0
        self.near_at = None
        self.covered = False
        self.hello_at = None
        self.buf = bytearray(7)
        self.level = 1.0
        self.target = 1.0

    def poll(self, now):
        if time.ticks_diff(now, self.next_poll) < 0:
            return 0
        self.next_poll = time.ticks_add(now, 100)
        try:
            if self.bus is None:
                self.bus = I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)
            if not self.connected:
                if self.bus.readfrom_mem(0x23, 0x86, 2) != b'\x92\x05':
                    raise OSError('Not an LTR559')
                # 1x gain, 100 ms integration / repeat; proximity at 100 ms.
                for register, value in ((0x80,1),(0x85,1),(0x81,0x23),
                                        (0x82,0x7b),(0x83,1),(0x84,2)):
                    self.bus.writeto_mem(0x23, register, bytes((value,)))
                self.connected = True
                self.light_at = now
                self.next_poll = time.ticks_add(now, 200)
                return 0
            # Read status before channels: reading channels clears ready bits.
            status = self.bus.readfrom_mem(0x23, 0x8c, 1)[0]
            self.bus.readfrom_mem_into(0x23, 0x88, self.buf)
            if status & 4 and not status & 128:
                ch1 = self.buf[0] | self.buf[1] << 8
                ch0 = self.buf[2] | self.buf[3] << 8
                ratio = ch1 * 100 / max(1, ch0 + ch1)
                if ratio < 45:
                    lux = (17743 * ch0 + 11059 * ch1) / 10000
                elif ratio < 64:
                    lux = (42785 * ch0 - 19548 * ch1) / 10000
                elif ratio < 85:
                    lux = (5926 * ch0 + 1185 * ch1) / 10000
                else:
                    lux = 0
                self.lux = max(0, lux)
                self.light_at = now
            event = 0
            if status & 1:
                self.proximity = (self.buf[5] | self.buf[6] << 8) & 2047
                high = max(180, self.baseline + 120)
                low = max(120, self.baseline + 60)
                if not self.near:
                    self.near_count = self.near_count + 1 if self.proximity > high else 0
                    if self.near_count >= 2:
                        self.near = True
                        self.near_at = now
                        if self.hello_at is None or time.ticks_diff(now, self.hello_at) > 5000:
                            event = HELLO
                            self.hello_at = now
                    elif self.proximity < high:
                        self.baseline += (self.proximity - self.baseline) * 0.05
                elif self.proximity < low:
                    event = REVEAL if self.covered else 0
                    self.near = self.covered = False
                    self.near_count = 0
                    self.near_at = None
                elif not self.covered and time.ticks_diff(now, self.near_at) >= 900:
                    self.covered = True
                    event = COVER
            if self.light_at is None or time.ticks_diff(now, self.light_at) > 3000:
                self.target = 1.0
            elif not self.near and self.lux is not None:
                self.target = min(1.0, 0.2 + (self.lux / 500) ** 0.5 * 0.8)
            return event
        except OSError:
            self.connected = self.near = self.covered = False
            self.near_count = 0
            self.near_at = self.light_at = self.lux = None
            self.baseline = 60.0
            self.target = 1.0
            self.next_poll = time.ticks_add(now, 2000)
            return 0

    def brightness(self, dt):
        # Time based fade; covers and reconnects cannot instantly black out UI.
        step = min(100, max(0, dt)) * 0.0003
        self.level += max(-step, min(step, self.target - self.level))
        return self.level
