"""Run with mpremote after uploading rom_fixtures.py into /lib.

Validates all four mixer channels without PWM, then plays the original
fixture for five seconds alongside full-resolution framebuffer updates.
"""
from array import array
import machine
import gbaudiocore as core
from rom_fixtures import gb_audio_rom
from gb_audio_probe import run

fb = bytearray(240 * 240 * 2)
block = array('I', [0] * core.audio_samples)
signatures = []
for route in (0, 0x11, 0x22, 0x44, 0x88, 0xff):
    rom = gb_audio_rom(route)
    core.init(rom)
    assert not core.frame(fb, 0, 0, 0, False)
    core.audio(block, 4095, 100)
    low, high = min(block), max(block)
    assert all((x & 65535) == 0 and (x >> 16) <= 4095 for x in block)
    assert (low == high) == (route == 0), (route, low, high)
    signatures.append(bytes(block))
    print('Mixer route/range:', route, low >> 16, high >> 16)
assert len(set(signatures)) == 6
core.audio(block, 4095, 0)
assert min(block) == max(block)
for bad in (bytearray(4), bytearray(core.audio_samples * 4 + 4)):
    try:
        core.audio(bad, 4095, 35)
        raise AssertionError('Invalid buffer accepted')
    except ValueError:
        pass
state = bytearray(core.state_size())
core.save_state(state)
core.audio(block, 4095, 100)
expected = bytes(block)
core.load_state(state)
core.audio(block, 4095, 100)
assert bytes(block) == expected
try:
    core.load_state(state[:-1])
    raise AssertionError('Short state accepted')
except ValueError:
    pass
del fb, block, signatures
before = machine.freq()
result = run(fixture=gb_audio_rom(), seconds=5)
assert result[0] > 200, result
assert machine.freq() == before
assert machine.Pin(43).value() == 0

# Verify the full-resolution renderer leaves both black bars intact in PSRAM.
fb = bytearray(480 * 480 * 2)
rom = gb_audio_rom()
core.init(rom)
core.palette(1, 2, 3, 4)
assert not core.frame(fb, 0, 0, 0, True, 1)
assert not any(memoryview(fb)[:24 * 480 * 2])
assert not any(memoryview(fb)[456 * 480 * 2:])
assert any(memoryview(fb)[24 * 480 * 2:456 * 480 * 2])
del fb

# Force a mixer failure after PWM/DMA creation; both resources must be released.
from rp2 import DMA
from gb_audio_probe import Output
original_audio = core.audio
original_init = Output.__init__
channels = []


def capture_init(self, rate):
    original_init(self, rate)
    channels.append(self.dma.channel)


def fail(*args):
    raise RuntimeError('intentional audio failure')


core.audio = fail
Output.__init__ = capture_init
try:
    try:
        run(fixture=gb_audio_rom(), seconds=1)
        raise AssertionError('Expected failure')
    except RuntimeError as error:
        assert str(error) == 'intentional audio failure'
finally:
    core.audio = original_audio
    Output.__init__ = original_init
assert machine.freq() == before
assert machine.Pin(43).value() == 0
claim = DMA()
assert claim.channel == channels[0]
claim.close()
print('Mixer, PWM/DMA, framebuffer and normal/error cleanup checks passed')
