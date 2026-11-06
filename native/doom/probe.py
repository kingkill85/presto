"""Finite, silent on-device Doomgeneric probe. Run with mpremote; not an app."""
import gc, os, time, machine
from presto import Presto
from game_launch import mount_sd
from scumm_files import ReadSession
from gamepad import Gamepad, A, B, X, Y, START, SELECT, LEFT, RIGHT, UP, DOWN
from retro_clock import EmulationClock

presto = Presto(full_res=True, direct_to_fb=True, layers=1, ambient_light=False)
presto.display.set_pen(0)
presto.display.clear()
mount_sd()
import doomcore
pad = Gamepad()
pad.poll()
print('pad', pad.connected, 'clock', machine.freq())
if not pad.connected:
    raise RuntimeError('Connect the gamepad before this diagnostic')
files = ReadSession()
clock = EmulationClock()
# Diagnostic settings; reset between runs.
DURATION_MS = 10000
TURBO = False
CAPTURE = True
CHECK_PSRAM = False
start = time.ticks_ms()
last_time = start
elapsed = 1
frames = 0
last_keys = 0
queue = []
keys = ((UP,0xad),(DOWN,0xaf),(LEFT,0xac),(RIGHT,0xae),(A,0xa3),(B,0xa2),(X,0xa0),(Y,0xa1),(START,13),(SELECT,27))

def callback(op, a, b):
    global elapsed, last_time, frames, last_keys
    if op < 100:
        # Diagnostic reads exactly the selected WAD; no config or saves.
        if op == 0 and a != '/sd/doom/doom1.wad':
            return 0
        return files(op,a,b)
    if op == 100:
        now=time.ticks_ms()
        elapsed += time.ticks_diff(now,last_time)
        last_time=now
        return elapsed
    if op == 101:
        time.sleep_ms(min(a,10))
        return 0
    if op == 102:
        if not queue:
            held=pad.poll()
            if not pad.connected:
                clock.pause()
                raise RuntimeError('Gamepad disconnected; diagnostic stopped')
            for mask,key in keys:
                if (held^last_keys)&mask:
                    queue.append(512 | (256 if held&mask else 0) | key)
            last_keys=held
        return queue.pop(0) if queue else 0
    if op == 103:
        frames+=1
        return 0
    return 0

gc.collect()
print('before arena', gc.mem_free())
arena=bytearray(5*1024*1024)
print('after arena', gc.mem_free())
try:
    doomcore.init(arena,callback,memoryview(presto.display),'/sd/doom/doom1.wad')
    print('INIT OK',gc.mem_free())
    if CHECK_PSRAM:
        import hashlib
        guard = bytearray(1024*1024)
        guard_view = memoryview(guard)
        pattern = bytes(range(256))*256
        for offset in range(0,len(guard),65536):
            guard_view[offset:offset+65536] = pattern
        guard_hash = hashlib.sha256(guard).digest()
    if TURBO:
        clock.resume()
    if CHECK_PSRAM:
        print('PSRAM before',hashlib.sha256(guard).digest()==guard_hash)
    print('game clock',machine.freq())
    # Setup/diagnostics are outside game time and outside the timed sample.
    last_time=time.ticks_ms()
    tic0=doomcore.frame()
    start=time.ticks_ms()
    frames=0
    while time.ticks_diff(time.ticks_ms(),start)<DURATION_MS:
        tic=doomcore.frame()
    duration=time.ticks_diff(time.ticks_ms(),start)
    print('RESULT frames',frames,'ms',duration,'fps',frames*1000/duration,'tics',tic-tic0,'free',gc.mem_free())
    if CHECK_PSRAM:
        print('PSRAM after',hashlib.sha256(guard).digest()==guard_hash)
    clock.pause()
    if CAPTURE:
        with open('/sd/doom/probe.rgb565','wb') as f:
            f.write(memoryview(presto.display))
finally:
    clock.pause()
    files.close()
    print('clock restored',machine.freq())
