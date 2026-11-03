# Hardware benchmark using a user's own ROM; no ROM is supplied.
# Set LABEL='NES', MATCH='Mario Bros. 3' or LABEL='SMS', MATCH='Sonic The Hedgehog (USA'
# before running via mpremote. Warm-up inputs target those two games only.
# Mario 3: wait for the map, move right then up onto 1, and enter with A.
# The default 120-frame stationary sample stays in level 1-1 (visually verified).
# Longer runs may die and return to the map; verify scenes before reporting FPS.
# Native core loading occurs inside retro.run, after ROM allocation, as in the app.
LABEL=globals().get('LABEL', 'NES')
MATCH=globals().get('MATCH', 'Mario Bros. 3')
FRAME_COUNT=globals().get('FRAME_COUNT',120 if LABEL == 'NES' else 960)
import time
import retro
# Optional clock comparison; leave unset to measure the app's normal turbo.
CPU_MHZ=globals().get('CPU_MHZ', None)
if CPU_MHZ is not None:
    from retro_clock import EmulationClock
    class BenchmarkClock(EmulationClock):
        def __init__(self):
            super().__init__()
            self.target=CPU_MHZ * 1000000
    retro.EmulationClock=BenchmarkClock
from retro_roms import load_core, discover
retro.mount_sd()
path=next(p for p in discover() if MATCH in p)
core=None
frames=drawn=0
started=last_draw=None
intervals=[]
timings=[0,0]
counts=[0,0]
pad_time=[0]
real_poll=retro.pad.poll
def poll(*args):
 t=time.ticks_us()
 result=real_poll(*args)
 pad_time[0]+=time.ticks_diff(time.ticks_us(),t)
 return result
retro.pad.poll=poll
class Finished(Exception):
    pass

def steps(count,keys):
    for i in range(count):
        assert not original_frame(retro.fb,keys,0,0,False,2)

def palette(*args):
    original_palette(*args)
    steps(480,0)
    steps(5,8)
    steps(90,0)
    if path.lower().endswith('.nes'):
        steps(5,8)
        steps(360,0)
        steps(20,16)
        steps(60,0)
        steps(20,64)
        steps(60,0)
        steps(5,1)
    steps(180,0)
    stats=getattr(core,'chr_stats',None)
    if stats: print('Warm-up CHR calls/decodes:',stats())
    print('Playing',LABEL)

def frame(fb,keys,x,y,draw,scale):
    global frames,drawn,started,last_draw,last_drawn
    now=time.ticks_us()
    if started is None:
        started=now
    if frames==FRAME_COUNT:
        raise Finished()
    if draw:
        assert last_drawn is None or frames - last_drawn >= 2
        last_drawn = frames
    if draw:
        if last_draw is not None:
            intervals.append(time.ticks_diff(now,last_draw))
        last_draw=now
    keys=0 if LABEL == 'NES' else 16 | (1 if frames%90 < 12 else 0)
    t=time.ticks_us()
    assert not original_frame(fb,keys,x,y,draw,scale)
    timings[bool(draw)]+=time.ticks_diff(time.ticks_us(),t)
    counts[bool(draw)]+=1
    frames+=1
    drawn+=bool(draw)
last_drawn=None
def actual_load(path):
    global core,original_frame,original_palette
    core,period=load_core(path)
    original_frame,original_palette=core.frame,core.palette
    core.frame,core.palette=frame,palette
    return core,period
retro.load_core=actual_load
try:
    retro.run(path)
except Finished:
    elapsed=time.ticks_diff(time.ticks_us(),started)
    print('RESULT',LABEL,'emulated FPS',round(frames*1000000/elapsed,2),
          'display FPS',round(drawn*1000000/elapsed,2))
    print('CORE us', [timings[i]//max(1,counts[i]) for i in range(2)], 'PAD us', pad_time[0]//frames)
    print('Draw interval ms min/mean/max:',min(intervals)//1000,
          sum(intervals)//len(intervals)//1000,max(intervals)//1000)
    assert 0 < drawn <= (FRAME_COUNT + 1) // 2
    # Report slow results rather than disguising them as a failed correctness test.
    print('Full speed:', frames*1000000/elapsed > 58)
    stats=getattr(core,'chr_stats',None)
    if stats: print('Measured CHR calls/decodes:',stats())
finally:
    if core: core.frame,core.palette=original_frame,original_palette
