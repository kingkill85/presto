"""Opt-in, bounded DMG mixed-audio experiment; not a launcher application.

run(path, seconds=15) accepts an existing monochrome GB ROM. No saves are
written. A missing path uses the original four-channel fixture supplied by
tests/gb_audio_device.py. Requires the separate gbaudiocore native module.
"""
import time
from machine import Pin, PWM, mem32
from rp2 import DMA

# RP2350 SDK: GPIO43 = PWM slice9/B, DREQ_PWM_WRAP9 = 41.
PWM_SLICE = 0x400a8000 + 9 * 0x14


class Output:
    """Finite transfers only: starvation cannot read beyond a Python buffer.

    The next frame is mixed while DMA plays the previous one. The Python
    handoff leaves a small measured gap; seamless DMA chaining is a later step.
    Clock changes require closing and recreating the output.
    """
    def __init__(self, rate):
        self.dma = None
        self.pwm = PWM(Pin(43), freq=rate, duty_u16=32768)
        try:
            self.top = mem32[PWM_SLICE + 0x10]
            self.dma = DMA()  # Claim through firmware; never steal display DMA.
            self.ctrl = self.dma.pack_ctrl(size=2, inc_read=True,
                                          inc_write=False, treq_sel=41,
                                          bswap=False)
            self.buffer = None
            self.last_submit = None
            self.gap_max_us = 0
            self.gap_total_us = 0
            self.period_us = 0
            self.rate = self.pwm.freq()
        except BaseException:
            self.close()
            raise

    def submit(self, buffer):
        deadline = time.ticks_add(time.ticks_ms(), 100)
        while self.dma.active():
            if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                raise RuntimeError('Audio DMA timeout')
            time.sleep_us(50)
        # Keep a strong reference throughout DMA, including between calls.
        self.buffer = buffer
        self.dma.config(read=buffer, write=PWM_SLICE + 0x0c,
                        count=len(buffer) // 4, ctrl=self.ctrl, trigger=True)
        now = time.ticks_us()
        if self.last_submit is not None:
            gap = max(0, time.ticks_diff(now, self.last_submit) - self.period_us)
            self.gap_max_us = max(self.gap_max_us, gap)
            self.gap_total_us += gap
        self.last_submit = now
        self.period_us = (len(buffer) // 4) * 1000000 // self.rate

    def close(self):
        if self.dma is not None:
            self.dma.active(0)
            self.dma.close()
            self.dma = None
        self.pwm.duty_u16(0)
        self.pwm.deinit()
        Pin(43, Pin.OUT, value=0)
        self.buffer = None


def run(path=None, seconds=15, fixture=None, volume=35):
    from presto import Presto
    from gamepad import Gamepad, START, SELECT
    from retro_clock import EmulationClock
    import gbaudiocore as core
    if not 1 <= seconds <= 60 or not 0 <= volume <= 100:
        raise ValueError('seconds 1..60; volume 0..100')
    presto = Presto(ambient_light=False, full_res=True, layers=1,
                    direct_to_fb=True)
    if path:
        import os
        rom = bytearray(os.stat(path)[6])
        with open(path, 'rb') as source:
            if source.readinto(rom) != len(rom):
                raise ValueError('Incomplete ROM')
    else:
        rom = fixture
    if rom is None or len(rom) < 0x150 or rom[0x143] & 0x80:
        raise ValueError('A monochrome Game Boy ROM is required')
    size = core.init(rom)
    ram = bytearray(size)
    core.set_ram(ram)
    display = presto.display
    fb = memoryview(display)
    core.palette(*(display.create_pen(*c) for c in
                   ((155, 188, 15), (139, 172, 15), (48, 98, 48), (15, 56, 15))))
    display.set_pen(display.create_pen(0, 0, 0))
    display.clear()
    presto.update()
    buffers = [bytearray(core.audio_samples * 4) for _ in range(2)]
    pad = Gamepad()
    clock = EmulationClock()
    output = None
    frames = 0
    max_work = total_work = 0
    late_frames = 0
    try:
        clock.resume()
        output = Output(core.audio_rate)
        started = time.ticks_ms()
        until = time.ticks_add(started, seconds * 1000)
        while time.ticks_diff(until, time.ticks_ms()) > 0:
            held = pad.poll()
            if path and not pad.connected:
                break  # This probe never advances a real game without a pad.
            if held & (START | SELECT) == START | SELECT:
                break
            before = time.ticks_us()
            err = core.frame(fb, held & 255, 0, 0, True, 1)
            if err:
                raise RuntimeError('Game Boy core error: %s' % err)
            block = buffers[frames & 1]
            core.audio(block, output.top, volume)
            presto.update()
            elapsed = time.ticks_diff(time.ticks_us(), before)
            total_work += elapsed
            max_work = max(max_work, elapsed)
            if elapsed > 16743:
                late_frames += 1
            output.submit(block)
            frames += 1
        elapsed_ms = time.ticks_diff(time.ticks_ms(), started)
        print('GB audio frames/ms:', frames, elapsed_ms,
              'work mean/max us:', total_work // max(1, frames), max_work,
              'late frames:', late_frames,
              'estimated DMA gap mean/max us:',
              output.gap_total_us // max(1, frames - 1), output.gap_max_us)
        return frames, elapsed_ms, max_work, late_frames
    finally:
        try:
            if output is not None:
                output.close()
        finally:
            clock.pause()
