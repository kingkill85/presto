import machine,time,audiofifo
from machine import mem32,PWM,Pin
from rp2 import DMA
from uctypes import addressof
from presto import Presto
p=Presto(full_res=False,layers=1,ambient_light=False)
source=[bytearray(1476),bytearray(1476)]
result=memoryview(p.presto)[115200:118152]
base=0x400c8000
assert mem32[base+0x18]==0 and mem32[base+8]&2
old=mem32[base+0x14]
ds=[DMA(),DMA()]
pwm=PWM(Pin(43),freq=22039,duty_u16=0)
try:
    for trial in range(20):
        for i in range(2):
            for j in range(1476):source[i][j]=(trial*19+i*67+j*37+j//256)&255
            audiofifo.clean(source[i])
            ds[i].config(read=0x50500000,write=result[i*1476:(i+1)*1476],count=369,ctrl=ds[i].pack_ctrl(size=2,inc_read=False,inc_write=True,treq_sel=41,chain_to=ds[i].channel))
        audiofifo.queue(source[0],-1,ds[0].channel)
        deadline=time.ticks_add(time.ticks_ms(),1000)
        while mem32[base+0x18]:
            assert time.ticks_diff(deadline,time.ticks_ms())>0
        if trial%2:time.sleep_ms(30)
        audiofifo.queue(source[1],ds[0].channel,ds[1].channel)
        while ds[0].active() or ds[1].active():
            assert time.ticks_diff(deadline,time.ticks_ms())>0
        assert bytes(result)==bytes(source[0])+bytes(source[1]),'sequence mismatch'
        assert mem32[base+0x18]==0 and mem32[base+8]&2
    print('PASS 20 paired streams, exact sample order, delayed handoffs, cache cleaning')
finally:
    for d in ds:d.active(0);d.close()
    pwm.deinit();Pin(43,Pin.OUT,value=0)
    mem32[base+0x18]=0
    for i in range(2):
        if not(mem32[base+8]&2):x=mem32[0x50500000]
    mem32[base+0x14]=old
