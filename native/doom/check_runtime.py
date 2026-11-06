"""Finite hardware check. Run twice: write five slots, then restore after reset.

Uses only /sd/saves/doom-hardware-test; never overwrites player slots.
Set DOOM_CHECK_RESTORE=True with mpremote exec before the second run.
"""
import gc
import json
import machine
import time
from doom_runtime import run

restore = globals().get('DOOM_CHECK_RESTORE', False)
root = '/sd/saves/doom-hardware-test'
state = {'slot': 1, 'tic': 0, 'expected': []}
boot_clock = machine.freq()


class TestPad:
    connected = True
    def poll(self, now=None):
        return 64 if state['slot'] <= 5 else 0  # UP


def hook(core, backend, slots, audio, clock):
    slot = state['slot']
    if slot > 5 or core.status()[0] - state['tic'] < 15:
        return
    backend.pad = TestPad()
    slots.root = root
    backend.paused = True
    audio.pause()
    clock.pause()
    assert machine.freq() == boot_clock
    if restore:
        if slot == 1:
            with open(root+'/expected.json') as f:
                state['expected'] = json.load(f)
        slots.load(slot)
        assert list(core.status()[1:]) == state['expected'][slot-1]
        print('RESTORED SLOT', slot, core.status()[1:])
    else:
        slots.save(slot)
        state['expected'].append(list(core.status()[1:]))
        print('SAVED SLOT', slot, core.status()[1:])
        if slot == 5:
            with open(root+'/expected.json', 'w') as f:
                json.dump(state['expected'], f)
    backend.display.set_palette(backend.display.palette_rgb)
    core.redraw()
    state['slot'] += 1
    state['tic'] = core.status()[0]
    gc.collect()
    backend.paused = False
    backend.reset_time()
    clock.resume()
    audio.resume()


run(duration=15000, hook=hook)
assert state['slot'] == 6
assert machine.freq() == boot_clock
print('DOOM FIVE-SLOT CHECK PASSED', 'restore' if restore else 'save')
