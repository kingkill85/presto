# Hardware-only clock/correctness check; use original fixtures, never game saves.
# timeout 50 mpremote mount tests + exec "KIND='NES'" + run tests/check_retro_clock_device.py + reset
# KIND: GB/GBC/GG/NES/SMS. Each kind should run after a fresh soft reset.
import binascii
import machine
import time
from rom_fixtures import gbc_rom, nes_rom, sega_rom
from presto import Presto

KIND = globals().get('KIND', 'NES')
TURBO_MHZ = globals().get('TURBO_MHZ', 300)
presto = Presto(ambient_light=False, full_res=True, layers=1, direct_to_fb=True)
display = presto.display
fb = memoryview(display)
normal = machine.freq()
watchdog = machine.WDT(timeout=8000)
core = __import__({'GB':'gbcore', 'GBC':'gbccore', 'NES':'nescore', 'SMS':'smscore', 'GG':'smscore'}[KIND])
rom = nes_rom() if KIND == 'NES' else sega_rom(KIND == 'GG') if KIND in ('SMS','GG') else gbc_rom()
if KIND == 'GB':
    rom[0x143] = 0
    rom[0x14d] = (-sum(rom[0x134:0x14d]) - 25) & 255
# Verify a megabyte of PSRAM remains intact through both clock changes.
sentinel = bytearray(bytes(range(256)) * 4096)
sentinel_crc = binascii.crc32(sentinel)
expected = None
try:
    for mhz in (normal // 1000000, TURBO_MHZ):
        watchdog.feed()
        machine.freq(mhz * 1000000)
        display.set_pen(display.create_pen(0,0,0)); display.clear()
        size = core.init(rom, KIND == 'GG') if KIND in ('SMS','GG') else core.init(rom)
        ram = bytearray(size)
        if size: core.set_ram(ram)
        core.palette(*(display.create_pen(*rgb) for rgb in ((155,188,15),(139,172,15),(48,98,48),(15,56,15))))
        start = time.ticks_us()
        for frame in range(360):
            if frame % 16 == 0: watchdog.feed()
            assert not core.frame(fb,0,0,0,frame % 2 == 0,2 if KIND in ('NES','SMS') else True)
            if frame % 2 == 0: presto.update()
        elapsed = time.ticks_diff(time.ticks_us(),start)
        checksum = binascii.crc32(fb)
        if expected is None: expected = checksum
        assert checksum == expected, 'Clock changed emulated image'
        assert binascii.crc32(sentinel) == sentinel_crc, 'PSRAM corruption'
        assert len(set(fb)) > 1, 'Blank image'
        print('PASS', KIND, mhz, 'MHz', 'CRC', hex(checksum), '360 frames ms', elapsed // 1000)
finally:
    machine.freq(normal)
    print('RESTORED', machine.freq() // 1000000)
