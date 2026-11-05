"""Bounded real console-loop check using only the original ROM fixture.

Exercises menu/state roundtrip, disconnect/resume and exception cleanup.
No user ROMs, saves or settings are changed.
"""
import time
import os
import machine
import psram
psram.mkramfs()
import retro
from rom_fixtures import gb_audio_rom
from retro_audio import Audio
path = '/ramfs/audio-fixture.gb'
try:
    os.remove(path)  # remove the earlier test fixture, if present
except OSError:
    pass
import gbaudiocore as core
original_read = retro.read_rom
original_load = retro.load_core
original_system = retro.system_for
retro.read_rom = lambda path: gb_audio_rom(0x33)
retro.load_core = lambda path: (core, 16743)
retro.system_for = lambda path: ('GB', 'gbaudiocore', 16743)
state_root = '/ramfs/audio-states'
original_poll = retro.pad.poll
original_address = retro.pad.address
original_frame = Audio.frame
original_pause = retro.ui.pause
original_wait = retro.wait_for_pad
frames = 0
disconnected = False
menu_checked = False
max_underruns = 0
normal = machine.freq()


class Finished(Exception):
    pass


def poll(*args):
    global disconnected
    retro.pad.address = 0x21
    if frames == 300 and not disconnected:
        retro.pad.address = None
        disconnected = True
    return 12 if frames == 200 else 0


def wait():
    assert machine.freq() == normal
    assert machine.Pin(43).value() == 0
    retro.pad.address = 0x21


def frame(self):
    global frames, max_underruns
    original_frame(self)
    frames += 1
    max_underruns = max(max_underruns, self.underruns)
    if frames >= 600:
        raise Finished()


def pause(title, zoom, slots, set_zoom, audio, set_volume):
    global menu_checked
    assert machine.freq() == normal
    assert machine.Pin(43).value() == 0
    assert not audio.channels
    slots.base = state_root
    slots.root = slots.base + '/fixture'
    for n in range(1, 6):
        slots.save(n)
        slots.load(n)
        os.remove(slots.path(n))
    os.rmdir(slots.root)
    os.rmdir(slots.base)
    menu_checked = True
    print('Menu mute and five audio states OK')
    return 'loaded', zoom


retro.pad.poll = poll
Audio.frame = frame
retro.ui.pause = pause
retro.wait_for_pad = wait
started = time.ticks_ms()
try:
    retro.run(path)
except Finished:
    pass
finally:
    retro.read_rom = original_read
    retro.load_core = original_load
    retro.system_for = original_system
    retro.pad.poll = original_poll
    retro.pad.address = original_address
    Audio.frame = original_frame
    retro.ui.pause = original_pause
    retro.wait_for_pad = original_wait
assert menu_checked and disconnected
assert machine.freq() == normal
assert machine.Pin(43).value() == 0
assert max_underruns == 0, max_underruns
print('Console lifecycle frames/ms/underruns:', frames,
      time.ticks_diff(time.ticks_ms(), started), max_underruns)
