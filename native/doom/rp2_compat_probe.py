"""Read-only compatibility probe for rp2040-doom's unmodified RP2350 build.

Run on Presto with mpremote. This does not start Doom or reassign hardware.
The short-pointer formula is from doomtype.h at upstream revision
29a453c980918a03e40fc8b69b024e7a3bdb5dc2. Test its preconditions without
calling ptr_to_shortptr(), whose invalid-input path executes a breakpoint.
"""
import gc
import os
import machine
import uctypes
from presto import Presto

BASE = 0x20030000
LIMIT = BASE + 0x40000


def representable(address):
    return BASE + 4 <= address < LIMIT and not (address & 3)


presto = Presto(full_res=True, direct_to_fb=True, layers=1, ambient_light=False)
fb = memoryview(presto.display)
gc.collect()
arena = bytearray(256 * 1024)
address = uctypes.addressof(arena)
framebuffer = uctypes.addressof(fb)
# Equivalent to the 16-bit cast and reconstruction, without dereferencing it.
encoded = ((address - BASE) >> 2) & 0xffff
decoded = BASE + encoded * 4 if encoded else 0
print('firmware', os.uname().release, os.uname().version)
print('clock', machine.freq())
print('arena', hex(address), 'bytes', len(arena))
print('upstream shortptr range', hex(BASE + 4), hex(LIMIT))
print('arena representable', representable(address))
print('hypothetical shortptr roundtrip', hex(decoded), decoded == address)
print('framebuffer', hex(framebuffer), 'bytes', len(fb))
overlap = max(0, min(framebuffer + len(fb), LIMIT) - max(framebuffer, BASE))
print('shortptr window overlapping active framebuffer bytes', overlap)
print('free heap', gc.mem_free())
print('No engine, second core, IRQ, DMA, voltage or clock changes performed')
