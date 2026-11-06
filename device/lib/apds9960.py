"""APDS-9960 gesture, proximity and colour sensor at 0x39, without blocking.

poll() reads colour/proximity and drains the gesture FIFO; a finished swipe
appears once in `gesture` (UP, DOWN, LEFT, RIGHT) for that poll. The decoding
follows SparkFun's approach: compare the up/down and left/right ratios of the
first and last strong samples of one pass over the sensor.
"""

import time

from machine import I2C, Pin

ADDRESS = 0x39
IDS = (0xAB, 0xA8, 0x9C)

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
# The breakout's orientation on the desk; swap if the arrows go the wrong way.
FLIP_UD = False
FLIP_LR = False

_THRESHOLD = 10    # sample counts below this are noise
_SENSITIVITY = 30  # minimum ratio change (percent points) for a swipe

_SETUP = (
    (0x80, 0x00),  # ENABLE: everything off while configuring
    (0x81, 0xDB),  # ATIME: 37 cycles, ~103 ms colour integration
    (0x83, 0xF6),  # WTIME
    (0x8E, 0x87),  # PPULSE: 16 us, 8 pulses
    (0x8F, 0x0A),  # CONTROL: LED 100 mA, proximity gain 4x, colour gain 4x
    (0x90, 0x01),  # CONFIG2: no LED boost
    (0x9F, 0x00),  # CONFIG3
    (0xA0, 40),    # GPENTH: gesture engine starts above this proximity
    (0xA1, 30),    # GEXTH: ... and stops below this
    (0xA2, 0x40),  # GCONF1: FIFO threshold 4 datasets, exit after 1
    (0xA3, 0x41),  # GCONF2: gain 4x, LED 100 mA, 2.8 ms wait
    (0xA4, 0), (0xA5, 0), (0xA7, 0), (0xA9, 0),  # offsets
    (0xA6, 0xC9),  # GPULSE: 32 us, 10 pulses
    (0xAA, 0x00),  # GCONF3: all four photodiodes
    (0xAB, 0x00),  # GCONF4: no interrupt, gesture mode left to the engine
    (0x80, 0x47),  # ENABLE: power, colour, proximity, gesture
)


class APDS9960:
    def __init__(self, bus=None):
        self.bus = bus
        self.ready = False
        self.retry_at = time.ticks_ms()
        self.colour = bytearray(8)
        self.fifo = bytearray(128)
        self.one = bytearray(1)
        self.proximity = 0
        self.clear = self.red = self.green = self.blue = 0
        self.udlr = (0, 0, 0, 0)  # latest gesture sample, for drawing
        self.gesture = None
        self._first = self._last = None

    @property
    def connected(self):
        return self.ready

    def _r8(self, reg):
        self.bus.readfrom_mem_into(ADDRESS, reg, self.one)
        return self.one[0]

    def _start(self):
        if self.bus is None:
            self.bus = I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)
        if self._r8(0x92) not in IDS:
            raise OSError("no APDS-9960")
        for reg, value in _SETUP:
            self.one[0] = value
            self.bus.writeto_mem(ADDRESS, reg, self.one)
        self.ready = True

    def poll(self, now=None):
        if now is None:
            now = time.ticks_ms()
        self.gesture = None
        try:
            if not self.ready:
                if time.ticks_diff(now, self.retry_at) < 0:
                    return
                self._start()
            status = self._r8(0x93)
            if status & 0x01:  # AVALID
                c = self.colour
                self.bus.readfrom_mem_into(ADDRESS, 0x94, c)
                self.clear = c[0] | c[1] << 8
                self.red = c[2] | c[3] << 8
                self.green = c[4] | c[5] << 8
                self.blue = c[6] | c[7] << 8
            if status & 0x02:  # PVALID
                self.proximity = self._r8(0x9C)
            self._gestures()
        except OSError:
            self.ready = False
            self.proximity = 0
            self.udlr = (0, 0, 0, 0)
            self._first = self._last = None
            self.retry_at = time.ticks_add(now, 2000)

    def _gestures(self):
        level = self._r8(0xAE) if self._r8(0xAF) & 1 else 0  # GFLVL if GVALID
        if level:
            n = min(level, 32) * 4
            view = memoryview(self.fifo)
            # In chunks: the shared bus' 2 ms timeout covers a whole transfer.
            for i in range(0, n, 32):
                self.bus.readfrom_mem_into(ADDRESS, 0xFC, view[i:min(n, i + 32)])
            f = self.fifo
            for i in range(0, n, 4):
                u, d, l, r = f[i], f[i + 1], f[i + 2], f[i + 3]
                self.udlr = (u, d, l, r)
                if u > _THRESHOLD and d > _THRESHOLD and l > _THRESHOLD and r > _THRESHOLD:
                    ratios = ((u - d) * 100 // (u + d), (l - r) * 100 // (l + r))
                    if self._first is None:
                        self._first = ratios
                    self._last = ratios
            return
        # The engine has left gesture mode (GMODE clear): the pass is over.
        if self._r8(0xAB) & 1:
            return
        self.udlr = (0, 0, 0, 0)
        if self._first is None:
            return
        ud = self._last[0] - self._first[0]
        lr = self._last[1] - self._first[1]
        self._first = self._last = None
        if max(abs(ud), abs(lr)) < _SENSITIVITY:
            return
        if abs(ud) > abs(lr):
            up = ud < 0
            if FLIP_UD:
                up = not up
            self.gesture = UP if up else DOWN
        else:
            right = lr > 0
            if FLIP_LR:
                right = not right
            self.gesture = RIGHT if right else LEFT

    def stop(self):
        try:
            if self.ready:
                self.one[0] = 0
                self.bus.writeto_mem(ADDRESS, 0x80, self.one)
        except OSError:
            pass
        self.ready = False
