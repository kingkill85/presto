import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pad_module = SimpleNamespace(Gamepad=object, A=1, B=2, START=8, SELECT=4,
                            RIGHT=16, LEFT=32, UP=64, DOWN=128, X=256, Y=512)
with patch.dict(sys.modules, {'gamepad':pad_module, 'game_ui':SimpleNamespace(GameUI=object),
    'game_launch':SimpleNamespace(mount_sd=lambda:None,take_request=lambda:{},launch=lambda *a:None),
    'scumm_audio':SimpleNamespace(Display=object,Audio=object,BUFFER_BYTES=32768),
    'retro_clock':SimpleNamespace(EmulationClock=object)}), \
    patch.object(sys,'path',[str(ROOT/'device/lib')]+sys.path):
    runtime = load('doom_runtime_test','device/lib/doom_runtime.py')

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.time=SimpleNamespace(ticks_ms=lambda:self.now,
            ticks_diff=lambda a,b:((a-b+(1<<29))%(1<<30))-(1<<29))
        p=patch.object(runtime,'time',self.time);p.start();self.addCleanup(p.stop)
        p=patch.dict(runtime.MenuChord.poll.__globals__,{'time':self.time});p.start();self.addCleanup(p.stop)
        self.held=0
        self.pad=SimpleNamespace(connected=True,poll=lambda now:self.held)
        self.touch=SimpleNamespace(state=False,y=0,poll=lambda:None)
        self.display=SimpleNamespace(touch=self.touch)
        self.core=SimpleNamespace(weapon_key=lambda:51)
        self.audio=SimpleNamespace(pump=lambda:None)
        self.backend=runtime.Backend(self.display,self.pad,self.core,self.audio,'/sd/doom/doom1.wad')

    def test_chord_consumed_and_held_keys_released(self):
        self.held=64;self.backend.input()
        self.assertEqual(self.backend.queue,[768|0xad]);self.backend.queue=[]
        self.held=64|4|8;self.backend.input()
        self.assertTrue(self.backend.menu_requested)
        self.assertEqual(self.backend.queue,[512|0xad])
        self.assertFalse(any((x&255) in (13,27) for x in self.backend.queue))

    def test_disconnect_releases_and_weapon_release_keeps_original_key(self):
        self.held=512;self.backend.input();self.assertEqual(self.backend.queue,[768|51])
        self.backend.queue=[];self.core.weapon_key=lambda:52
        self.pad.connected=False;self.backend.input()
        self.assertTrue(self.backend.disconnected)
        self.assertEqual(self.backend.queue,[512|51])

    def test_wrapping_clock_and_paused_clock(self):
        self.backend.last_time=(1<<30)-10;self.now=10
        self.assertEqual(self.backend(100,0,0),21)
        self.now=1000;self.backend.reset_time();self.now=1010
        self.assertEqual(self.backend(100,0,0),31)
        self.backend.paused=True;self.now=2000
        self.assertEqual(self.backend(100,0,0),31)
        self.backend.paused=False;self.now=2010
        self.assertEqual(self.backend(100,0,0),41)

    def test_wad_boundary_rejects_other_files(self):
        with patch.object(self.backend,'files') as files:
            self.assertEqual(self.backend(0,'/secrets.py',None),0)
            files.assert_not_called()

    def test_corrupt_state_rejected_before_native_restore(self):
        core=SimpleNamespace(state_id='test',state_size=lambda:8,
            save_state=lambda b:b.__setitem__(slice(None),b'12345678'),
            capabilities=lambda:1)
        restored=[];core.load_state=lambda b:restored.append(bytes(b))
        slots=runtime.DoomSlots('/sd/doom/doom1.wad',core,'identity')
        with tempfile.TemporaryDirectory() as root:
            slots.base=root;slots.root=root+'/game'
            with patch.dict(slots.save.__globals__,{'stamp':lambda:'test'}):slots.save(1)
            slots.load(1);self.assertEqual(restored,[b'12345678'])
            p=Path(slots.path(1));data=p.read_bytes();p.write_bytes(data[:-1]+b'X')
            with self.assertRaises(ValueError):slots.load(1)
            self.assertEqual(len(restored),1)
            with self.assertRaises(ValueError):slots.path(6)

if __name__=='__main__':unittest.main()
