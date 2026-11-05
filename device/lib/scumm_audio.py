"""SCUMM's indexed scanout and SRAM audio queue for Presto firmware v1.0.0."""
import micropython
from array import array
from machine import mem32
from uctypes import addressof, bytearray_at
from presto import Presto
from picographics import PicoGraphics, DISPLAY_PRESTO_FULL_RES, PEN_P8
from retro_audio import Audio as DMAAudio

PIXELS = 480 * 480
PCM_SAMPLES = 4096
PWM_SAMPLES = PCM_SAMPLES * 2
BUFFER_BYTES = PWM_SAMPLES * 4


class _DisplayPriority:
    """Temporarily prioritize the verified PIO1 display DMA chain, not its IRQs."""
    def __init__(self):
        self.saved = []

    def enable(self):
        if self.saved:
            return
        pixels = []
        for channel in range(16):
            base = 0x50000000+channel*64
            target = mem32[base+4]
            if 0x50300010 <= target <= 0x5030001c and mem32[base+12] & 1:
                pixels.append(channel)
        reloads = [0x50000000+channel*64+0x3c for channel in pixels]
        channels = pixels+[channel for channel in range(16)
                           if mem32[0x50000000+channel*64+4] in reloads]
        if len(pixels) != 2 or len(channels) != 4:
            raise RuntimeError('Unsupported Presto display DMA layout')
        for channel in channels:
            base = 0x50000000+channel*64
            control = mem32[base+0x10]
            self.saved.append((base, control & 2, mem32[base+4]))
            # AL1_CTRL is non-triggering. Preserve configuration and do not
            # write back error-status bits (which can be write-one-to-clear).
            mem32[base+0x10] = (control & 0x1fffffff) | 2

    def restore(self):
        for base, priority, target in self.saved:
            if mem32[base+4] == target:
                mem32[base+0x10] = (mem32[base+0x10] & 0x1ffffffd) | priority
        self.saved = []


class Display(Presto):
    def __init__(self):
        super().__init__(full_res=True, palette=True, layers=1, ambient_light=False)
        back = memoryview(self.presto)
        # v1.0.0 Presto_get_framebuffer returns the second half of its static
        # 460800-byte SRAM allocation in P8 mode. The first half is scanout.
        # Keep the driver alive; never free either non-owning memory view.
        address = addressof(back)
        if len(back) != PIXELS or not (0x20000000 <= address-PIXELS and address+PIXELS <= 0x20082000):
            raise RuntimeError('Unsupported Presto indexed framebuffer layout')
        self.front = bytearray_at(address-PIXELS, PIXELS)
        self.display = PicoGraphics(DISPLAY_PRESTO_FULL_RES, pen_type=PEN_P8,
                                    layers=1, buffer=self.front)
        self.audio_buffers = (back[:BUFFER_BYTES], back[BUFFER_BYTES:BUFFER_BYTES*2])
        self.game_pen_type = PEN_P8
        self.palette_dirty = True
        self.palette_rgb = bytearray(768)
        self.audio_priority = _DisplayPriority()

    def set_palette(self, rgb):
        if len(rgb) != 768:
            raise ValueError('Invalid SCUMM palette')
        self.palette_rgb[:] = rgb
        for i in range(256):
            j = i * 3
            self.display.update_pen(i, rgb[j], rgb[j+1], rgb[j+2])
        self.palette_dirty = True

    def update(self):
        # The native renderer writes directly to scanout. Only palette changes
        # require the firmware update/vsync; copying every frame stalls audio.
        if self.palette_dirty:
            super().update()
            self.palette_dirty = False
        else:
            self.touch_poll()


# One-pole high-pass, Q15: y = A*(y' + x - x'), fc = fs/(2*pi)*(1-A)/A, ~400 Hz
# at 22.05 kHz. The piezo cannot play bass; removing it frees PWM range.
HP_A = 29415


@micropython.viper
def _expand(buf, top: int, state, volume: int) -> int:
    # state: array('i', [gain Q8, x', y']) kept across blocks (filter memory).
    words = ptr32(buf)
    st = ptr32(state)
    middle = top // 2
    a = int(HP_A)
    gain = int(st[0])
    x0 = int(st[1])
    y0 = int(st[2])
    # Pass 1: loudness of the filtered block as mean absolute value.
    xp = x0
    yp = y0
    total = 0
    for i in range(4096):
        x = int(words[i] >> 16)-middle
        y = (a*(yp+x-xp)) >> 15
        xp = x
        yp = y
        total += y if y >= 0 else -y
    mean = total >> 12
    # Normalize the mean level to 30% of full scale (peak normalization left
    # AdLib music at ~25% RMS). At most 16x: after the high-pass, MI2 music
    # sat at the former 6x cap almost always. Attack at once; release ~6% per
    # block so quiet passages and fades rise gradually.
    target = 4096 if mean < 1 else (middle*77)//mean
    if target > 4096:
        target = 4096
    if target < gain:
        gain = target
    else:
        step = (gain >> 4)+1
        gain = target if target < gain+step else gain+step
    # Pass 2: filter again from the same state, scale and soft-limit peaks
    # (1:4 above 60%, hard stop at 95%), written in place as duty words.
    knee = (middle*60)//100
    limit = (middle*95)//100
    xp = x0
    yp = y0
    for i in range(4096):
        x = int(words[i] >> 16)-middle
        y = (a*(yp+x-xp)) >> 15
        xp = x
        yp = y
        m = y if y >= 0 else -y
        m = (((m*gain) >> 8)*volume)//100  # no 32-bit overflow at 16x
        if m > knee:
            m = knee+((m-knee) >> 2)
            if m > limit:
                m = limit
        level = middle+m if y >= 0 else middle-m
        words[i] = level << 16
    st[0] = gain
    st[1] = xp
    st[2] = yp
    # Backwards expansion preserves unread samples. Doubling samples puts
    # the PWM carrier at 44.1 kHz without changing the 22.05 kHz music tempo.
    for j in range(4096):
        i = 4095-j
        w = words[i]
        words[i*2] = w
        words[i*2+1] = w
    return gain


class _Source:
    audio_samples = PWM_SAMPLES
    audio_rate = 44100

    def __init__(self, core, buffers):
        if core.audio_samples != 1024 or core.audio_rate != 22050:
            raise ValueError('Unsupported SCUMM mixer format')
        self.core = core
        self.state = array('i', [256, 0, 0])  # gain Q8, high-pass memory
        self.buffers = buffers
        self.parts = tuple(tuple(b[i:i+4096] for i in range(0,16384,4096)) for b in buffers)
        self.reset()

    def reset(self):
        self.part = 0
        self.prepared = None

    def prepare(self, block, top, volume):
        parts = self.parts[0 if block is self.buffers[0] else 1]
        self.core.audio(parts[self.part], top, 100)
        self.part += 1
        if self.part < len(parts):
            return False
        _expand(block, top, self.state, volume)
        self.prepared = block
        return True

    def audio(self, block, top, volume):
        # DMAAudio.frame() queues only a completely prepared buffer.
        if self.prepared is not block:
            raise RuntimeError('SCUMM audio buffer is not ready')
        self.reset()


class Audio(DMAAudio):
    def __init__(self, core, display, volume):
        source = _Source(core, display.audio_buffers)
        super().__init__(source, volume)
        self.buffers = display.audio_buffers
        self.display = display
        self.mixing = False
        self.suspended = False
        self.blocks = 0

    def pause(self):
        self.suspended = True
        super().pause()
        self.core.reset()
        self.display.audio_priority.restore()

    def resume(self):
        super().resume()
        try:
            self.display.audio_priority.enable()
            self.suspended = False
        except BaseException:
            self.pause()
            raise

    def pump(self):
        if self.mixing or self.suspended:
            return
        if not self.channels:
            self.resume()
        if self.channels[self.index].active():
            return
        self.mixing = True
        try:
            # Generate one 46 ms mixer chunk per safe engine callback, rather
            # than blocking animation while computing the entire queue block.
            if self.core.prepare(self.buffers[self.index], self.top, self.volume):
                self.frame()
                self.blocks += 1
        finally:
            self.mixing = False
