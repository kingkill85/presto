"""Interactive SCUMM audio check; skips the intro and defaults to three minutes.

PROFILE=1/2, DURATION and VOLUME can be supplied with mpremote exec before run.
AUDIO_TEST_CORE selects an isolated native module before deployment.
"""
import sys
import time
import machine
from uctypes import addressof

if 'AUDIO_TEST_CORE' in globals():
    sys.modules['scummcore'] = __import__(AUDIO_TEST_CORE)
from scumm_backend import Backend, run
from scumm_audio import Audio

original_call = Backend.__call__
original_init = Audio.__init__
seen = []
events = [(2500, (1,27,27)), (2530, (2,27,27)),
          (5500, (1,27,27)), (5530, (2,27,27))]
normal = machine.freq()


def audio_init(self, core, display, volume):
    original_init(self, core, display, globals().get('VOLUME', 100))
    for block in self.buffers:
        assert 0x20000000 <= addressof(block) < 0x20082000


def callback(self, op, a, b):
    if not seen:
        seen.append(self)
    if op == 103 and events and self.now() >= events[0][0]:
        return events.pop(0)[1]
    return original_call(self, op, a, b)


Backend.__call__ = callback
Audio.__init__ = audio_init
try:
    profile = globals().get('PROFILE', 2)
    path = '/sd/scumm/monkey-vga-de' if profile == 1 else '/sd/scumm/monkey2-de'
    assert run(path=path, profile=profile, duration=globals().get('DURATION', 180)) == 0
    backend = seen[0]
    assert backend.audio.blocks > 25 and backend.frames > 30
    assert not backend.audio.channels and backend.audio.pwm is None
    assert not backend.presto.audio_priority.saved
    assert machine.freq() == normal and machine.Pin(43).value() == 0
    print('PASS SCUMM audio: SRAM buffers, game run, DMA cleanup and unchanged clock')
finally:
    Backend.__call__ = original_call
    Audio.__init__ = original_init
    if globals().get('RESET_AFTER', True):
        time.sleep_ms(500)
        machine.reset()
