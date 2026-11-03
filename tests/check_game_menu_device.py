# Real NES frame loop and shared menu; original fixture, no user ROM/saves.
import sys
sys.path.insert(0,'/')
import machine
import time
from rom_fixtures import nes_rom
import retro
import nescore

class Done(Exception):pass
normal=machine.freq()
started=time.ticks_ms()
choices=[3,0,5]  # zoom off, resume, exit
menus=0
modes=set()
frames=0
original_frame=nescore.frame

class Pad:
    connected=True
    pressed=actions=0
    def poll(self,now=None):
        elapsed=time.ticks_diff(time.ticks_ms(),started)
        return 12 if (menus==0 and elapsed>1000) or (menus==2 and elapsed>2300) else 0


def choose(title,rows,detail='',selected=0,back='Zurueck'):
    global menus
    assert machine.freq()==normal,'Menu running overclocked'
    assert rows[1][2] and rows[2][2], 'NES state slots must be available'
    value=choices.pop(0)
    retro.ui.draw(title,rows,value,detail,back)
    before=frames
    time.sleep_ms(60)
    assert frames==before,'Game advanced in menu'
    menus+=1
    return value


def frame(*args):
    global frames
    frames+=1
    modes.add(args[5])
    return original_frame(*args)


def launch(app,request):
    assert app=='games.py'
    assert request['system']=='NES'
    raise Done()

retro.pad=Pad()
retro.ui.pad=retro.pad
retro.ui.choose=choose
retro.ui.release=lambda:None
retro.launch=launch
retro.read_rom=lambda path:nes_rom()
retro.zoom_for=lambda path:True
retro.store_zoom=lambda path,value:None
nescore.frame=frame
try:
    retro.run('/fixture.nes')
except Done:
    pass
finally:
    nescore.frame=original_frame
assert not choices and modes=={1,2}
assert machine.freq()==normal
print('PASS NES real menu: SELECT+START, paused frames, zoom, library exit, clock restored')
