"""Exercise real SCUMM save/load in an isolated directory, never user slots."""
import os
import scummcore
from scumm_backend import Backend, FileSession, ScummSlots, run
from game_ui import GameUI

ROOT='/sd/scumm/menu-test-saves'
PROFILE=globals().get('PROFILE',1)
original_call=Backend.__call__
original_init=FileSession.__init__
original_path=FileSession.path
original_slots=ScummSlots.__init__
original_choose=GameUI.choose
original_release=GameUI.release
stages=[]
steps=[]
reads=[]
events=[(2000,(1,27,27)),(2030,(2,27,27)),(5000,(1,27,27)),(5030,(2,27,27))]


def init(self,save_root=ROOT):
    try:os.mkdir(ROOT)
    except OSError:pass
    original_init(self,save_root)


def path(self,p):
    p=original_path(self,p)
    if p.startswith('/sd/scumm/saves/'):
        p=ROOT+p[len('/sd/scumm/saves'):]
    return p


def slots_init(self,fn,profile):
    original_slots(self,fn,profile)
    self.prefix=self.prefix.replace('/sd/scumm/saves',ROOT)


def choose(self,title,rows,detail='',selected=0,back='Zurueck'):
    selected=steps.pop(0)
    self.draw(title,rows,selected,detail,back)
    assert rows[selected][2], 'Unexpected disabled action'
    return selected


def check(self,op,a,b):
    self.now()
    if op==0 and isinstance(a,str) and '.s05' in a:
        reads.append(a)
    if op==103:
        if events and self.elapsed>=events[0][0]:return events.pop(0)[1]
        caps=scummcore.state(0,0)
        if not stages and self.elapsed>=10000 and caps&1:
            steps.extend((1,4))  # actual shared menu -> save -> slot5
            self.pause_menu()
            stages.append('save requested')
        elif len(stages)==1 and self.elapsed>=16000 and caps&2:
            filename=ROOT+'/presto-'+('monkey-vga-de' if PROFILE==1 else 'monkey2-de')+'.s05'
            assert os.stat(filename)[6]>1000,'Save missing/incomplete'
            steps.extend((2,4))  # actual shared menu -> load -> slot5
            self.pause_menu()
            stages.append('load requested')
    result=original_call(self,op,a,b)
    if op==103 and result and result[0]==10:
        assert len(stages)==2 and reads, 'Save/load not completed'
    return result

FileSession.__init__=init
FileSession.path=path
ScummSlots.__init__=slots_init
GameUI.choose=choose
GameUI.release=lambda self:None
Backend.__call__=check
try:
    path='/sd/scumm/monkey-vga-de' if PROFILE==1 else '/sd/scumm/monkey2-de'
    assert run(path=path,profile=PROFILE,duration=25)==0
    print('PASS SCUMM slots/menu',PROFILE,stages,'loaded files',len(reads))
finally:
    Backend.__call__=original_call
    FileSession.__init__=original_init
    FileSession.path=original_path
    ScummSlots.__init__=original_slots
    GameUI.choose=original_choose
    GameUI.release=original_release
    for name in os.listdir(ROOT):os.remove(ROOT+'/'+name)
    os.rmdir(ROOT)
