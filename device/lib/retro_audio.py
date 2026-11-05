"""Finite, forward-only DMA audio queue for the Presto's GPIO43 piezo."""
import time
from machine import PWM, Pin, mem32
from rp2 import DMA
from uctypes import addressof

SLICE = 0x400a8000 + 9 * 0x14
# Frames per queued block. The XIP streamer holds one block at a time, so a
# block must be appended right when its predecessor has drained: one-frame
# blocks leave no slack and every frame slower than 16.7 ms (GBC drawing)
# underruns. Two-frame blocks let a slow drawn frame borrow from the next.
BLOCK_FRAMES = 2


class Audio:
    def __init__(self, core, volume=60):
        self.core = core
        self.volume = volume
        self.buffers = [bytearray(core.audio_samples * 4 * BLOCK_FRAMES) for _ in range(2)]
        self.channels = []
        self.pwm = None
        self.index = 0
        self.underruns = 0
        self.started = False
        self.primed = False
        self.stream = False
        self.stream_owned = False
        self.slack_us = 0  # time the last queued block waited for playback

    def resume(self):
        self.pause()
        try:
            # SCUMM supplies SRAM buffers and keeps its direct DMA path.
            self.stream = 0x11000000 <= addressof(self.buffers[0]) < 0x11800000
            if self.stream:
                import audiofifo
                self.fifo = audiofifo
                if mem32[0x400c8018] or not (mem32[0x400c8008] & 2):
                    raise RuntimeError('XIP audio stream already in use')
                self.stream_address = mem32[0x400c8014]
                self.stream_owned = True
            self.pwm = PWM(Pin(43), freq=self.core.audio_rate, duty_u16=32768)
            self.top = mem32[SLICE + 0x10]
            self.channels.append(DMA())
            self.channels.append(DMA())
            self.controls = [d.pack_ctrl(size=2, inc_read=not self.stream, inc_write=False,
                                        treq_sel=41, bswap=False) for d in self.channels]
            self.links = [d.pack_ctrl(default=self.controls[i],
                                      chain_to=self.channels[1-i].channel)
                          for i, d in enumerate(self.channels)]
            # Subclasses may supply one-frame buffers; then whole blocks are used.
            size = self.core.audio_samples * 4
            self.per = len(self.buffers[0]) // size
            self.parts = [[b] if self.per == 1 else
                          [memoryview(b)[k * size:(k + 1) * size] for k in range(self.per)]
                          for b in self.buffers]
            self.part = 0
            self.index = 0
            self.started = False
            self.primed = False
        except BaseException:
            self.pause()
            raise

    def frame(self):
        # One call per emulated frame; a block is queued once all its parts are
        # filled. Returns True if it had to wait for playback: the caller is then
        # exactly on time and must not sleep on a second clock.
        i = self.index
        if self.part == 0 and not self.stream:
            # Direct DMA reads this buffer itself: wait until it is played.
            self._wait(self.channels[i])
        # Streamed buffers are free once the streamer drained them, which
        # the previous queue call waited for.
        self.core.audio(self.parts[i][self.part], self.top, self.volume)
        self.part += 1
        if self.part < self.per:
            return False
        self.part = 0
        if self.stream:
            return self._stream_queue()
        current = self.channels[i]
        previous = self.channels[1 - i]
        # Remove the old link BEFORE rearming: the queue never forms a cycle.
        # The final queued channel chains to itself (hardware: no chaining).
        block = self.buffers[i]
        current.config(read=block, write=SLICE + 0x0c,
                       count=self.core.audio_samples * self.per, ctrl=self.controls[i])
        if not self.started:
            if not self.primed:
                self.primed = True
                self.index = 1 - i
                return False
            previous.config(ctrl=self.links[1-i], trigger=True)
            self.started = True
            self.index = 1 - i
            return False
        if previous.active():
            previous.config(ctrl=self.links[1-i])
        # Also covers a completion racing the link update. The read pointer
        # distinguishes an unstarted block from a completed one (count writes
        # update the reload value, not the visible remaining count).
        if not previous.active() and not current.active() and current.read == addressof(block):
            if self.started:
                self.underruns += 1
            current.config(trigger=True)
        self.started = True
        self.index = 1 - i
        return False

    def _wait(self, channel):
        deadline = time.ticks_add(time.ticks_ms(), 100)
        waited = False
        while channel.active():
            if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                raise RuntimeError('Audio DMA timeout')
            time.sleep_us(50)
            waited = True
        return waited

    def _stream_queue(self):
        i = self.index
        current = self.channels[i]
        previous = self.channels[1-i]
        start = time.ticks_us()
        waited = self._wait(current)
        deadline = time.ticks_add(time.ticks_ms(), 100)
        block = self.buffers[i]
        self.fifo.clean(block)
        current.config(read=0x50500000, write=SLICE + 0x0c,
                       count=self.core.audio_samples * self.per, ctrl=self.controls[i])
        # Counter zero means the previous block's final samples are in the
        # FIFO. Keep those samples: the next stream appends behind them.
        while mem32[0x400c8018]:
            if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                raise RuntimeError('Audio FIFO timeout')
            time.sleep_us(10)
            waited = True
        self.slack_us = time.ticks_diff(time.ticks_us(), start) if waited else 0
        self.underruns += self.fifo.queue(block,
                                         previous.channel if self.started else -1,
                                         current.channel)
        self.started = True
        self.index = 1-i
        return waited

    def pause(self):
        # Disable both links before aborting/releasing either channel.
        for d in self.channels:
            d.config(ctrl=d.pack_ctrl(enable=False, chain_to=d.channel))
        for d in self.channels:
            d.active(0)  # Abort: close() only unclaims in MicroPython 1.26.
            d.close()
        self.channels = []
        if self.stream_owned:
            mem32[0x400c8018] = 0
            for _ in range(2):
                if not (mem32[0x400c8008] & 2):
                    _discard = mem32[0x50500000]
            mem32[0x400c8014] = self.stream_address
            self.stream_owned = False
        if self.pwm is not None:
            self.pwm.duty_u16(0)
            self.pwm.deinit()
            self.pwm = None
            Pin(43, Pin.OUT, value=0)
