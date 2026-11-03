import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import sys
from test_gamepad import Clock

LIB=Path(__file__).resolve().parents[1]/'device/lib'
PAD=SimpleNamespace(SELECT=4,START=8,A=1,B=2,UP=64,DOWN=128,LEFT=32,RIGHT=16)


def load(name, **stubs):
    spec=importlib.util.spec_from_file_location(name,LIB/(name+'.py'))
    mod=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,stubs), patch.object(sys,'path',[str(LIB)]+sys.path):
        spec.loader.exec_module(mod)
    return mod


class ChordTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.mod=load('game_controls',time=self.clock,gamepad=PAD)
        self.chord=self.mod.MenuChord()

    def test_chord_is_consumed_once_and_requires_release(self):
        self.assertEqual(self.chord.poll(4,0),(0,False))
        self.assertEqual(self.chord.poll(12,40),(0,True))
        self.assertEqual(self.chord.poll(12,200),(0,False))
        self.assertEqual(self.chord.poll(8,300),(0,False))
        self.assertEqual(self.chord.poll(0,400),(0,False))
        self.assertEqual(self.chord.poll(12,500),(0,True))

    def test_single_buttons_are_delayed_but_short_taps_survive(self):
        self.assertEqual(self.chord.poll(8,0),(0,False))
        self.assertEqual(self.chord.poll(0,40),(8,False))
        self.assertEqual(self.chord.poll(0,60),(0,False))
        self.assertEqual(self.chord.poll(4,100),(0,False))
        self.assertEqual(self.chord.poll(4,220),(4,False))
        self.assertEqual(self.chord.poll(4,240),(4,False))
        self.assertEqual(self.chord.poll(0,260),(0,False))

    def test_tick_wrap_and_xy_are_normal_inputs(self):
        self.assertEqual(self.chord.poll(8,(1<<30)-50),(0,False))
        self.assertEqual(self.chord.poll(8,80),(8,False))
        self.chord.poll(0,100)
        self.assertEqual(self.chord.poll(256|512,120),(768,False))


class SlotTests(unittest.TestCase):
    def setUp(self):
        self.mod=load('game_storage')
        self.mod.stamp=lambda:'03.11.2026 23:00'
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data=bytearray(b'ABCD')
        self.loads=[]
        self.core=SimpleNamespace(state_id='fixture-v1',state_size=lambda:4,
            save_state=lambda out:out.__setitem__(slice(None),self.data),
            load_state=lambda data:self.loads.append(bytes(data)))
        self.slots=self.mod.StateSlots('/roms/game.gb',self.core,b'rom',self.temp.name)

    def test_five_independent_slots_and_game_isolation(self):
        for n in range(1,6):
            self.data[:]=bytes((n,))*4
            self.slots.save(n)
        for n in range(1,6):
            self.slots.load(n)
            self.assertEqual(self.loads[-1],bytes((n,))*4)
            self.assertEqual(self.slots.info(n),'03.11.2026 23:00')
        other=self.mod.StateSlots('/roms/other.gb',self.core,b'rom',self.temp.name)
        self.assertIsNone(other.info(1))
        with self.assertRaises(ValueError):self.slots.path(6)
        with self.assertRaises(ValueError):self.slots.path(0)

    def test_corruption_or_other_rom_never_reaches_core(self):
        self.slots.save(1)
        path=Path(self.slots.path(1))
        original=path.read_bytes()
        path.write_bytes(original[:-1]+b'Z')
        with self.assertRaises(ValueError):self.slots.load(1)
        self.assertFalse(self.loads)
        path.write_bytes(original)
        self.slots.identity='wrong rom'
        with self.assertRaises(ValueError):self.slots.load(1)
        self.assertFalse(self.loads)

    def test_failed_overwrite_preserves_old_slot_and_recovers_backup(self):
        self.slots.save(1)
        path=self.slots.path(1)
        old=Path(path).read_bytes()
        rename=self.mod.os.rename
        def failing(src,dst):
            if src.endswith('.tmp'):raise OSError('disk failure')
            rename(src,dst)
        self.data[:]=b'NEXT'
        with patch.object(self.mod.os,'rename',side_effect=failing):
            with self.assertRaises(OSError):self.slots.save(1)
        self.assertEqual(Path(path).read_bytes(),old)
        rename(path,path+'.bak')
        self.slots.load(1)
        self.assertEqual(self.loads[-1],b'ABCD')

    def test_missing_core_support_is_explicit(self):
        slots=self.mod.StateSlots('/roms/game.nes',SimpleNamespace(),b'rom',self.temp.name)
        self.assertEqual(slots.capabilities(),(False,False))
        with self.assertRaises(ValueError):slots.save(1)


class LibraryTests(unittest.TestCase):
    def test_virtual_folders_use_detected_system_and_only_installed_games(self):
        roms=SimpleNamespace(discover=lambda:['/roms/color.gb','/roms/plain.gb'],
            system_for=lambda p:('GBC' if p.endswith('color.gb') else 'GB',None,0))
        cat=load('game_catalog',retro_roms=roms)
        cat.installed_adventures=lambda:[cat.SCUMM_GAMES[1]]
        folders=cat.catalog()
        self.assertEqual([f[0] for f in folders],['GB','GBC','SCUMM'])
        self.assertEqual(folders[1][2][0]['path'],'/roms/color.gb')
        self.assertEqual(folders[2][2][0]['profile'],1)


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.mod=load('game_ui',gamepad=PAD,picographics=SimpleNamespace(PicoGraphics=None,DISPLAY_PRESTO_FULL_RES=None,PEN_RGB565=None))
        self.ui=self.mod.GameUI(None,None)
        self.ui.release=lambda:None
        self.saved=[];self.loaded=[]
        self.slots=SimpleNamespace(capabilities=lambda:(True,True),info=lambda i:'old' if i==1 else None,
            save=self.saved.append,load=self.loaded.append)

    def test_overwrite_cancel_returns_to_menu_without_writing(self):
        steps=iter((1,0,0,0)) # save, slot1, cancel, resume
        self.ui.choose=lambda *a,**k:next(steps)
        result=self.ui.pause('game',True,self.slots,lambda v:None)
        self.assertEqual(result,('resume',True))
        self.assertFalse(self.saved)

    def test_zoom_and_slot_selection(self):
        steps=iter((3,1,4)) # zoom off, save, slot5
        self.ui.choose=lambda *a,**k:next(steps)
        changed=[]
        self.assertEqual(self.ui.pause('game',True,self.slots,changed.append),('saved',False))
        self.assertEqual(changed,[False]);self.assertEqual(self.saved,[5])

    def test_disabled_slots_and_empty_load_slots(self):
        rows=[]
        self.slots.capabilities=lambda:(False,False)
        self.ui.choose=lambda title,opts,*a,**k:rows.extend(opts) or 0
        self.ui.pause('game',True,self.slots,lambda v:None)
        self.assertFalse(rows[1][2]);self.assertFalse(rows[2][2])
        self.assertTrue(rows[3][2])
