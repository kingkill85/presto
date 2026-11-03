# Original fixtures only. One kind per reset; no user saves are touched.
# mpremote mount tests + exec "KIND='GB'" + run tests/check_game_states_device.py + reset
import machine
import time
import binascii
from presto import Presto
from rom_fixtures import gbc_rom, sega_rom, nes_rom

KIND=globals().get('KIND','GB')
p=Presto(full_res=True,direct_to_fb=True,layers=1,ambient_light=False)
fb=memoryview(p.display)
wdt=machine.WDT(timeout=8000)
core=__import__({'GB':'gbcore','GBC':'gbccore','GG':'smscore','SMS':'smscore','NES':'nescore'}[KIND])
rom=nes_rom() if KIND=='NES' else sega_rom(KIND=='GG') if KIND in ('GG','SMS') else gbc_rom()
if KIND=='GB':
    rom[0x143]=0
    rom[0x14d]=(-sum(rom[0x134:0x14d])-25)&255
size=core.init(rom,KIND=='GG') if KIND in ('GG','SMS') else core.init(rom)
ram=bytearray(size)
if size: core.set_ram(ram)
core.palette(*(p.display.create_pen(*rgb) for rgb in ((155,188,15),(139,172,15),(48,98,48),(15,56,15))))
large=1 if KIND in ('GB','GBC') else 2
small=2 if KIND in ('GB','GBC') else 1
for i in range(90):
    wdt.feed()
    assert not core.frame(fb,0,0,0,True,large)
a=bytearray(core.state_size())
b=bytearray(len(a))
c=bytearray(len(a))
core.save_state(a)
for i in range(12):
    wdt.feed()
    core.frame(fb,1 if i<4 else 0,0,0,True,large)
core.save_state(b)
crc=binascii.crc32(fb)
core.load_state(a)
for i in range(12):
    wdt.feed()
    core.frame(fb,1 if i<4 else 0,0,0,True,large)
core.save_state(c)
assert b==c, 'Restored simulation differs'
assert crc==binascii.crc32(fb), 'Restored pixels differ'
# Native reinit must restore callbacks/mappings rather than file pointers.
core.init(rom,KIND=='GG') if KIND in ('GG','SMS') else core.init(rom)
if size: core.set_ram(ram)
core.load_state(a)
for i in range(12):
    wdt.feed()
    core.frame(fb,1 if i<4 else 0,0,0,True,large)
core.save_state(c)
assert b==c, 'Reinit/restore differs'
p.display.set_pen(p.display.create_pen(0,0,0));p.display.clear()
core.frame(fb,0,0,0,True,small)
assert any(fb), 'Unscaled image blank'
# All handheld 1x images must be centred in 480x480, never in a 240px stride.
if KIND not in ('SMS','NES'):
    for y in range(480):
        if y%30==0:wdt.feed()
        row=fb[y*960:(y+1)*960]
        if y<168 or y>=312:assert not any(row), 'Vertical border'
        else:assert not any(row[:320]) and not any(row[640:]), 'Horizontal border'
p.update()
print('PASS',KIND,'states',len(a),'bytes; deterministic restore, reinit, integer zoom')
