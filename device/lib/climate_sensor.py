"""Optional BME280: forced measurements split across frames, values in C/%/hPa.
Compensation equations from Bosch's BME280 datasheet, section 8.1.
https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/
"""
import struct
import time
from machine import I2C, Pin


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


class ClimateSensor:
    def __init__(self, bus=None):
        self.bus = bus
        self.phase = 'connect'
        self.next_poll = time.ticks_ms()
        self.deadline = self.next_poll
        self.values = None
        self.buf = bytearray(8)

    def poll(self, now):
        if time.ticks_diff(now, self.next_poll) < 0:
            return
        try:
            if self.bus is None:
                self.bus = I2C(0, sda=Pin(40), scl=Pin(41), freq=400000, timeout=2000)
            if self.phase == 'connect':
                if self.bus.readfrom_mem(0x76, 0xd0, 1) != b'\x60':
                    raise OSError('Not a BME280')
                self.bus.writeto_mem(0x76, 0xe0, b'\xb6')
                self.phase = 'calibrate'
                self.deadline = time.ticks_add(now, 200)
                self.next_poll = time.ticks_add(now, 10)
            elif self.phase == 'calibrate':
                if self.bus.readfrom_mem(0x76, 0xf3, 1)[0] & 1:
                    if time.ticks_diff(now, self.deadline) >= 0:
                        raise OSError('BME280 startup timeout')
                    self.next_poll = time.ticks_add(now, 10)
                    return
                data = self.bus.readfrom_mem(0x76, 0x88, 26)
                self.t = struct.unpack('<Hhh', data[:6])
                self.p = struct.unpack('<Hhhhhhhhh', data[6:24])
                h = self.bus.readfrom_mem(0x76, 0xe1, 7)
                self.h = (data[25], struct.unpack('<h', h[:2])[0], h[2],
                          signed(h[3] << 4 | h[4] & 15, 12),
                          signed(h[5] << 4 | h[4] >> 4, 12), signed(h[6], 8))
                if not self.t[0] or not self.p[0]:
                    raise OSError('Invalid calibration')
                self.bus.writeto_mem(0x76, 0xf2, b'\x01')
                self.phase = 'start'
                self.next_poll = now
            elif self.phase == 'start':
                # 1x temperature/pressure/humidity, forced mode (~10 ms).
                self.bus.writeto_mem(0x76, 0xf4, b'\x25')
                self.phase = 'read'
                self.deadline = time.ticks_add(now, 200)
                self.next_poll = time.ticks_add(now, 20)
            else:
                if self.bus.readfrom_mem(0x76, 0xf3, 1)[0] & 9:
                    if time.ticks_diff(now, self.deadline) >= 0:
                        raise OSError('BME280 measurement timeout')
                    self.next_poll = time.ticks_add(now, 10)
                    return
                self.bus.readfrom_mem_into(0x76, 0xf7, self.buf)
                b = self.buf
                raw_p = b[0] << 12 | b[1] << 4 | b[2] >> 4
                raw_t = b[3] << 12 | b[4] << 4 | b[5] >> 4
                raw_h = b[6] << 8 | b[7]
                if raw_t == 0x80000 or raw_p == 0x80000 or raw_h == 0x8000:
                    raise OSError('BME280 sample not ready')
                self.values = self.compensate(raw_t, raw_p, raw_h)
                self.phase = 'start'
                self.next_poll = time.ticks_add(now, 5000)
        except (OSError, ValueError, ZeroDivisionError):
            self.values = None
            self.phase = 'connect'
            self.next_poll = time.ticks_add(now, 2000)

    def compensate(self, raw_t, raw_p, raw_h):
        t1, t2, t3 = self.t
        fine = (raw_t / 16384 - t1 / 1024) * t2 + (raw_t / 131072 - t1 / 8192) ** 2 * t3
        temperature = fine / 5120
        p1, p2, p3, p4, p5, p6, p7, p8, p9 = self.p
        a = fine / 2 - 64000
        b = (a * a * p6 / 32768 + a * p5 * 2) / 4 + p4 * 65536
        a = (1 + (p3 * a * a / 524288 + p2 * a) / 524288 / 32768) * p1
        pressure = (1048576 - raw_p - b / 4096) * 6250 / a
        pressure += (p9 * pressure * pressure / 2147483648 + pressure * p8 / 32768 + p7) / 16
        h1, h2, h3, h4, h5, h6 = self.h
        delta = fine - 76800
        humidity = (raw_h - (h4 * 64 + h5 * delta / 16384)) * (h2 / 65536 *
                   (1 + h6 * delta / 67108864 * (1 + h3 * delta / 67108864)))
        humidity *= 1 - h1 * humidity / 524288
        if not (-40 <= temperature <= 85 and 30000 <= pressure <= 110000):
            raise ValueError('Invalid climate sample')
        return round(temperature, 1), round(max(0, min(100, humidity))), round(pressure / 100)
