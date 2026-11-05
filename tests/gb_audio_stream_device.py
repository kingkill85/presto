"""Hardware check: finite chained DMA, starvation recovery, clock cleanup."""
import time, machine
from uctypes import addressof
from presto import Presto
p = Presto(ambient_light=False, full_res=True, layers=1, direct_to_fb=True)
import gbaudiocore as core
from rom_fixtures import gb_audio_rom
from retro_audio import Audio
from retro_clock import EmulationClock
rom = gb_audio_rom(0x33)
core.init(rom)
core.palette(0,1,2,3)
fb = memoryview(p.display)
clock = EmulationClock()
a = Audio(core, 30)
normal = machine.freq()
try:
    clock.resume()
    a.resume()
    start = time.ticks_ms()
    for n in range(180):
        core.frame(fb, 0, 0, 0, True, 1)
        a.frame()
        p.update()
    print('buffered frames/ms/underruns',180,time.ticks_diff(time.ticks_ms(),start),a.underruns)
    assert a.underruns == 0
    time.sleep_ms(100)
    for i,d in enumerate(a.channels):
        assert not d.active()
        assert d.count == 0
        expected = 0x50500000 if a.stream else addressof(a.buffers[i]) + len(a.buffers[i])
        assert d.read == expected, (i,d.read,expected)
    for n in range(10):
        core.frame(fb,0,0,0,False,1)
        a.frame()
    assert a.underruns == 1
    print('starvation recovery', a.underruns)
finally:
    a.pause()
    clock.pause()
assert machine.freq() == normal
assert machine.Pin(43).value()==0
print('DMA bounds and cleanup OK')
