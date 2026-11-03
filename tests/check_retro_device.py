# Run from the repository root, for example:
# mpremote mount tests + exec "KIND='GBC'" + run tests/check_retro_device.py
# KIND may be GBC, GG, SMS or NES. This uses only original test programs.
import gc, time
from rom_fixtures import gbc_rom, nes_rom, sega_rom
KIND = globals().get('KIND', 'GBC')
SCALE = globals().get('SCALE', 1)
MODULE = {'GBC':'gbccore','GG':'smscore','SMS':'smscore','NES':'nescore'}[KIND]
from presto import Presto
presto=Presto(ambient_light=False,full_res=True,layers=1,direct_to_fb=True)
d=presto.display
fb=memoryview(d)
d.set_pen(d.create_pen(0,0,0)); d.clear()
core=__import__(MODULE)
rom=gbc_rom() if KIND=='GBC' else nes_rom() if KIND=='NES' else sega_rom(KIND=='GG')
size=core.init(rom,KIND=='GG') if KIND in ('GG','SMS') else core.init(rom)
ram=bytearray(size)
if size:
    core.set_ram(ram)
    get_ram=getattr(core,'get_ram',None)
    if get_ram:
        live=get_ram()
        live[0]=73
        assert get_ram()[0]==73
pens=[d.create_pen(*rgb) for rgb in ((155,188,15),(139,172,15),(48,98,48),(15,56,15))]
core.palette(*pens)
for i in range(180):
    assert not core.frame(fb,0,0,0,False,SCALE if KIND in ('NES','SMS') else True)
start=time.ticks_us()
for i in range(90):
    assert not core.frame(fb,0,0,0,True,SCALE if KIND in ('NES','SMS') else True)
elapsed=time.ticks_diff(time.ticks_us(),start)
presto.update()
x,y=(0,24) if KIND in ('GBC','GG') else (112,120) if KIND=='NES' else (112,144)
if SCALE == 2 and KIND in ('NES','SMS'):
    x,y=0,0 if KIND=='NES' else 48
pixels=[]
for i in range(12):
    off=(y*480+x+i)*2
    pixels.append(fb[off]|fb[off+1]<<8)
print(KIND,'pixels:',[hex(p) for p in pixels])
assert len(set(pixels))>=2, 'Blank test image'
if SCALE==2 and KIND in ('NES','SMS'):
    assert pixels[0]==pixels[1] and pixels[2]==pixels[3] and pixels[0]!=pixels[2]
if KIND in ('GBC','GG'):
    assert pixels[0]==pixels[1]==pixels[2]
    assert pixels[3]==pixels[4]==pixels[5]
    assert pixels[0]!=pixels[3]
    assert fb[:24*480*2]==bytes(24*480*2)
print('PASS',KIND,'CPU/video/integer scaling/save RAM; mean us',elapsed//90,'raw FPS',round(90000000/elapsed,1))
