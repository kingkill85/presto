"""Validate installed NES games without touching battery saves or user slots.
SMB3 enters stage 1-1 using the previously verified map-input sequence.
"""
import machine
import time
import os
import binascii
from presto import Presto
from game_launch import mount_sd
from retro_roms import discover
import nescore as core

p=Presto(full_res=True,direct_to_fb=True,layers=1,ambient_light=False)
fb=memoryview(p.display)
mount_sd()
wdt=machine.WDT(timeout=8000)
normal=machine.freq()

def steps(count,keys):
    for i in range(count):
        wdt.feed()
        assert not core.frame(fb,keys,0,0,False,2)

try:
    machine.freq(300000000)
    for path in discover():
        if not path.lower().endswith('.nes'):continue
        machine.freq(normal)
        rom=bytearray(os.stat(path)[6])
        with open(path,'rb') as f:assert f.readinto(rom)==len(rom)
        core.init(rom)
        machine.freq(300000000)
        steps(480,0);steps(5,8);steps(90,0)
        if 'Mario Bros. 3' in path:
            steps(5,8);steps(360,0);steps(20,16);steps(60,0)
            steps(20,64);steps(60,0);steps(5,1);steps(180,0)
        else:
            steps(5,8);steps(180,0)
        p.display.set_pen(p.display.create_pen(0,0,0));p.display.clear()
        core.frame(fb,0,0,0,True,2);p.update()
        if 'Mario Bros. 3' in path:
            machine.freq(normal)
            with open('/sd/nes-state-smb3.rgb','wb') as f:
                for i in range(0,len(fb),4096):wdt.feed();f.write(fb[i:i+4096])
            machine.freq(300000000)
        initial=bytearray(core.state_size())
        expected=bytearray(len(initial));actual=bytearray(len(initial))
        core.save_state(initial)
        pixels=[]
        for i in range(60):
            wdt.feed()
            core.frame(fb,17 if i<20 else 0,0,0,i%2==0,2)
            if i%10==0:pixels.append(binascii.crc32(fb));p.update()
        core.save_state(expected)
        core.init(rom)
        core.load_state(initial)
        restored=[]
        for i in range(60):
            wdt.feed()
            core.frame(fb,17 if i<20 else 0,0,0,i%2==0,2)
            if i%10==0:restored.append(binascii.crc32(fb));p.update()
        core.save_state(actual)
        if expected!=actual:
            print('DIFF',[(i,expected[i],actual[i]) for i in range(len(actual)) if actual[i]!=expected[i]][:12])
        assert expected==actual,'Game state differs after load'
        assert pixels==restored,'Gameplay image differs after load'
        print('PASS installed NES',path.rsplit('/',1)[-1],len(initial),'bytes')
finally:
    machine.freq(normal)
