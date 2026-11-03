"""Run via mpremote after uploading native/scumm/scummprobe.mpy to /lib.

Original synthetic data only. This is a runtime test, not a playable engine.
"""
import gc
import machine
import os
import time
import scummprobe
from scumm_files import ReadSession

wdt = machine.WDT(timeout=8000)
arena = bytearray(128 * 1024)
calls = 0


def collect():
    global calls
    garbage = [bytearray(257) for _ in range(16)]
    del garbage
    gc.collect()
    calls += 1
    wdt.feed()


def interrupt():
    raise ValueError('injected callback failure')


start = time.ticks_ms()
try:
    assert scummprobe.self_test() == 1
    for session in range(3):
        assert scummprobe.runtime_test(arena, collect, 100) == 1
    try:
        scummprobe.runtime_test(arena, interrupt, 1)
        raise AssertionError('callback exception was swallowed')
    except ValueError as error:
        assert str(error) == 'injected callback failure'
    finally:
        scummprobe.close()
    # Retry after callback failure, including leaked native objects reclaimed
    # by closing the entire arena. Python's arena stays alive throughout.
    assert scummprobe.runtime_test(arena, collect, 100) == 1
    # Exhaustion must raise, then permit another fresh arena session.
    small = bytearray(16384)
    try:
        scummprobe.runtime_test(small, collect, 1)
        raise AssertionError('small arena unexpectedly accepted')
    except RuntimeError as error:
        assert str(error) == 'SCUMM arena exhausted'
    finally:
        scummprobe.close()
    assert scummprobe.runtime_test(arena, collect, 1) == 1
    print('PASS SCUMM runtime:', calls, 'GC callbacks,',
          time.ticks_diff(time.ticks_ms(), start), 'ms, clock', machine.freq())
finally:
    scummprobe.close()

# Mount using the application's existing SPI pins/driver. No game files change.
# Avoid importing the retro app, which also initializes its display/gamepad.
import sdcard
try:
    os.stat('/sd')
except OSError:
    spi = machine.SPI(0, sck=machine.Pin(34, machine.Pin.OUT),
                      mosi=machine.Pin(35, machine.Pin.OUT),
                      miso=machine.Pin(36, machine.Pin.OUT))
    os.mount(sdcard.SDCard(spi, machine.Pin(39), baudrate=8000000), '/sd')
os.stat('/sd')  # Fail explicitly when no card is present.
path = '/sd/.scumm-runtime-test-%d.bin' % time.ticks_ms()
try:
    os.stat(path)
except OSError:
    pass
else:
    raise RuntimeError('Refusing to overwrite existing test file')
session = ReadSession()
reads = 0


def io_callback(op, handle, value):
    global reads
    wdt.feed()
    # Force GC with a native buffer wrapped in a Python object still live.
    gc.collect()
    if op == 2:
        reads += 1
    return session(op, handle, value)


try:
    block = bytes((i * 17) & 255 for i in range(256))
    with open(path, 'wb') as stream:
        for _ in range(128):
            stream.write(block)
    for _ in range(3):
        result = scummprobe.file_test(arena, io_callback, path)
        assert result == 1, result
        assert not session.files
    assert scummprobe.file_test(arena, io_callback, path + '.missing') == -20
    assert not session.files
    print('PASS SCUMM SD streams:', reads, 'buffered/direct reads')
finally:
    session.close()
    scummprobe.close()
    os.remove(path)
