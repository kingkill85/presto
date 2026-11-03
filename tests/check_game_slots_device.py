# Two runs separated by reset: PHASE='write', then PHASE='load'. Original ROM only.
import os
import sys
sys.path.insert(0, "/")  # mpremote mount changes cwd; prefer the fixed root SD driver
import json
from game_launch import mount_sd
from game_storage import StateSlots, hexhash
from presto import Presto
from rom_fixtures import gbc_rom, nes_mapper_rom
KIND=globals().get('KIND','GB')
core=__import__('nescore' if KIND=='NES' else 'gbcore')
p=Presto(full_res=True,direct_to_fb=True,layers=1,ambient_light=False)
mount_sd()
if KIND=='NES':
    rom=nes_mapper_rom(4,False)
else:
    rom=gbc_rom();rom[0x143]=0;rom[0x14d]=(-sum(rom[0x134:0x14d])-25)&255
core.init(rom)
core.palette(1,2,3,4)
slots=StateSlots('presto-fixture.'+('nes' if KIND=='NES' else 'gb'),core,rom,root='/sd/.presto-slot-test')
fb=memoryview(p.display)
phase=globals().get('PHASE','write')
if phase=='write':
    checks=[]
    for slot in range(1,6):
        for i in range(3+slot):core.frame(fb,0,0,0,True,1)
        data=bytearray(core.state_size());core.save_state(data)
        checks.append(hexhash(data))
        slots.save(slot)
    with open('/sd/.presto-slot-test/checks.json','w') as f:json.dump(checks,f)
    print('PASS',KIND,'five on-disk slots written')
else:
    # Different allocations and a new native module address after reset.
    padding=bytearray(23457)
    with open('/sd/.presto-slot-test/checks.json') as f:checks=json.load(f)
    for slot in range(1,6):
        slots.load(slot)
        data=bytearray(core.state_size());core.save_state(data)
        assert hexhash(data)==checks[slot-1],'Cross-reset state differs'
        assert slots.info(slot)
        core.frame(fb,0,0,0,True,2)
        os.remove(slots.path(slot))
    os.rmdir(slots.root)
    os.remove('/sd/.presto-slot-test/checks.json')
    os.rmdir('/sd/.presto-slot-test')
    print('PASS',KIND,'five slots survive reset, load exactly and execute')
