# All supported mappers, using original fixtures; no user saves touched.
import machine
import binascii
from presto import Presto
from rom_fixtures import nes_mapper_rom
import nescore as core

p=Presto(full_res=True,direct_to_fb=True,layers=1,ambient_light=False)
fb=memoryview(p.display)
wdt=machine.WDT(timeout=8000)
normal=machine.freq()
machine.freq(300000000)
try:
    for mapper,chr_ram in ((0,False),(0,True),(1,False),(1,True),(2,True),(3,False),(4,False),(7,True)):
        rom=nes_mapper_rom(mapper,chr_ram)
        size=core.init(rom)
        ram=bytearray(size)
        core.set_ram(ram)
        for frame in range(43):
            wdt.feed()
            core.frame(fb,frame&1,0,0,True,2)
        start=bytearray(core.state_size())
        expected=bytearray(len(start))
        actual=bytearray(len(start))
        core.save_state(start)
        checks=[]
        for i in range(17):
            wdt.feed()
            core.frame(fb,(i*13)&0xff,0,0,i%3!=1,2)
            if i%3!=1:checks.append(binascii.crc32(fb))
        core.save_state(expected)
        # Round trip after a fresh cartridge init, recreating all host pointers.
        core.init(rom);core.set_ram(ram)
        core.load_state(start)
        core.save_state(actual)
        assert actual==start, 'Immediate snapshot differs'
        restored=[]
        for i in range(17):
            wdt.feed()
            core.frame(fb,(i*13)&0xff,0,0,i%3!=1,2)
            if i%3!=1:restored.append(binascii.crc32(fb))
        core.save_state(actual)
        if actual!=expected:
            print('DIFF',[(i,expected[i],actual[i]) for i in range(len(actual)) if actual[i]!=expected[i]][:12])
        assert actual==expected,'Mapper/CPU state diverged'
        assert checks==restored,'Rendered frames diverged'
        # Corrupt metadata and PRG/PPU bank offsets must fail before mutation.
        # Fixed v1 header: magic,version,size,ROM hash,mapper,16-byte NES header.
        for offset in (0,4,8,12,16,36,52):
            damaged=bytearray(start);damaged[offset]^=1
            try:core.load_state(damaged)
            except ValueError:pass
            else:raise AssertionError('Bad state accepted')
            core.save_state(actual)
            assert actual==expected,'Rejected state mutated the game'
        try:core.load_state(start[:-1])
        except ValueError:pass
        else:raise AssertionError('Truncated state accepted')
        different=bytearray(rom);different[-1]^=1
        core.init(different)
        try:core.load_state(start)
        except ValueError:pass
        else:raise AssertionError('Wrong ROM state accepted')
        print('PASS mapper',mapper,'CHR-RAM' if chr_ram else 'CHR-ROM',len(start),'bytes')
    print('PASS all NES mapper state round trips')
finally:
    machine.freq(normal)
