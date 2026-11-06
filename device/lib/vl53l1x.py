"""VL53L1X time-of-flight distance sensor at 0x29, without blocking.

A port of the register sequence of ST's ultra lite driver (ULD): the default
configuration block, continuous ranging, data-ready polling. poll() is meant
for every frame; it returns a new reading (mm, status) or None.
"""

import time

from machine import I2C, Pin

ADDRESS = 0x29
MODEL_ID = 0xEACC

# ULD VL51L1X_DEFAULT_CONFIGURATION, registers 0x2d..0x87 (ranging not started).
_CONFIG = bytes((
    0x00, 0x00, 0x00, 0x01, 0x02, 0x00, 0x02, 0x08, 0x00, 0x08, 0x10, 0x01,
    0x01, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x0F, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x20, 0x0B, 0x00, 0x00, 0x02, 0x0A, 0x21, 0x00, 0x00, 0x05, 0x00,
    0x00, 0x00, 0x00, 0xC8, 0x00, 0x00, 0x38, 0xFF, 0x01, 0x00, 0x08, 0x00,
    0x00, 0x01, 0xCC, 0x0F, 0x01, 0xF1, 0x0D, 0x01, 0x68, 0x00, 0x80, 0x08,
    0xB8, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x89, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x01, 0x0F, 0x0D, 0x0E, 0x0E, 0x00, 0x00, 0x02, 0xC7, 0xFF,
    0x9B, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
))

# Raw RESULT__RANGE_STATUS to the ULD status: 0 valid, 1 sigma, 2 signal,
# 4 out of bounds (too far/no target), 7 wrap-around; 255 other.
_STATUS = (255, 255, 255, 5, 2, 4, 1, 7, 3, 0, 255, 255, 9, 13, 255, 255,
           255, 255, 10, 6, 255, 255, 11, 12)

OK, SIGMA, SIGNAL, OUT_OF_RANGE, WRAP = 0, 1, 2, 4, 7


class VL53L1X:
    def __init__(self, bus=None):
        self.bus = bus
        self.ready = False
        self.retry_at = time.ticks_ms()
        self.buf = bytearray(17)
        self.one = bytearray(1)
        self.ready_bit = 1

    def _w8(self, reg, value):
        self.one[0] = value
        self.bus.writeto_mem(ADDRESS, reg, self.one, addrsize=16)

    def _r8(self, reg):
        self.bus.readfrom_mem_into(ADDRESS, reg, self.one, addrsize=16)
        return self.one[0]

    def _r16(self, reg):
        b = self.bus.readfrom_mem(ADDRESS, reg, 2, addrsize=16)
        return b[0] << 8 | b[1]

    def _start(self):
        if self.bus is None:
            self.bus = I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)
        if self._r16(0x010F) != MODEL_ID:
            raise OSError("no VL53L1X")
        # Soft reset, then wait (briefly, once) for the firmware to boot.
        self._w8(0x0000, 0x00)
        time.sleep_us(100)
        self._w8(0x0000, 0x01)
        start = time.ticks_ms()
        while True:
            time.sleep_ms(2)
            try:
                if self._r8(0x00E5) & 1:
                    break
            except OSError:  # NAKs while its firmware boots
                pass
            if time.ticks_diff(time.ticks_ms(), start) > 500:
                raise OSError("VL53L1X boot")
        # In chunks: the shared bus' 2 ms timeout covers a whole transfer.
        for i in range(0, len(_CONFIG), 16):
            self.bus.writeto_mem(ADDRESS, 0x002D + i, _CONFIG[i:i + 16], addrsize=16)
        # Data ready is GPIO__TIO_HV_STATUS bit 0 == the inverted polarity bit.
        self.ready_bit = 0 if self._r8(0x0030) & 0x10 else 1
        # First measurement for the VHV calibration, then the ULD's fixups.
        self._w8(0x0087, 0x40)
        start = time.ticks_ms()
        while self._r8(0x0031) & 1 != self.ready_bit:
            if time.ticks_diff(time.ticks_ms(), start) > 500:
                raise OSError("VL53L1X first range")
            time.sleep_ms(2)
        self._w8(0x0086, 0x01)
        self._w8(0x0087, 0x00)
        self._w8(0x0008, 0x09)
        self._w8(0x000B, 0x00)
        self._w8(0x0087, 0x40)  # continuous ranging from here on
        self.ready = True

    def poll(self, now=None):
        """(distance mm, status) when a new measurement arrived, else None.
        A missing sensor is retried every two seconds."""
        if now is None:
            now = time.ticks_ms()
        try:
            if not self.ready:
                if time.ticks_diff(now, self.retry_at) < 0:
                    return None
                self._start()
            if self._r8(0x0031) & 1 != self.ready_bit:
                return None
            self.bus.readfrom_mem_into(ADDRESS, 0x0089, self.buf, addrsize=16)
            self._w8(0x0086, 0x01)
            raw = self.buf[0] & 0x1F
            status = _STATUS[raw] if raw < len(_STATUS) else 255
            return (self.buf[13] << 8 | self.buf[14]), status
        except OSError:
            self.ready = False
            self.retry_at = time.ticks_add(now, 2000)
            return None

    def stop(self):
        try:
            if self.ready:
                self._w8(0x0087, 0x00)
        except OSError:
            pass
        self.ready = False
