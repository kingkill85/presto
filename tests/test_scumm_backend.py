import importlib.util
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Pad:
    buttons = 0

    def poll(self, now):
        return self.buttons


pad_module = SimpleNamespace(Gamepad=Pad, A=1, B=2, START=8, SELECT=4,
                            RIGHT=16, LEFT=32, UP=64, DOWN=128, X=256, Y=512)
files = load('scumm_files_test', ROOT/'device/lib/scumm_files.py')
with patch.dict('sys.modules', {'machine': SimpleNamespace(), 'gamepad': pad_module,
                               'scumm_files': files}), patch.object(sys, 'path', [str(ROOT/'device/lib')]+sys.path):
    backend_module = load('scumm_backend_test', ROOT/'device/lib/scumm_backend.py')


class FileBackendTests(unittest.TestCase):
    def test_installed_game_selection_and_explicit_profile(self):
        with patch.object(backend_module.os, 'stat', return_value=(0,) * 10):
            self.assertEqual(backend_module.choose_game(), ('/sd/scumm/monkey2-de', 2))
        def partial(path):
            if path.endswith('monkey2.001'):
                raise OSError('incomplete installation')
            return (0,) * 10
        with patch.object(backend_module.os, 'stat', side_effect=partial):
            self.assertEqual(backend_module.choose_game(), ('/sd/scumm/monkey-vga-de', 1))
        self.assertEqual(backend_module.choose_game('/sd/scumm/monkey-vga-de', 1),
                         ('/sd/scumm/monkey-vga-de', 1))
        with self.assertRaises(ValueError):
            backend_module.choose_game('/sd/scumm/atlantis-demo', 99)
        with self.assertRaises(ValueError):
            backend_module.choose_game('/sd/scumm/atlantis-demo', 0)
        self.assertEqual(backend_module.choose_game('/sd/scumm/monkey2-de'),
                         ('/sd/scumm/monkey2-de', 2))
        with patch.object(backend_module.os, 'stat', side_effect=OSError()):
            self.assertFalse(backend_module.installed_games())
            with self.assertRaises(OSError):
                backend_module.choose_game()

    def test_save_write_boundary_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            saves = Path(root)/'saves'
            saves.mkdir()
            outside = Path(root)/'game.001'
            outside.write_bytes(b'game data')
            session = backend_module.FileSession(str(saves))
            self.assertEqual(session(10, str(saves/'../game.001'), None), 0)
            self.assertNotEqual(session(14, str(outside), None), 0)
            self.assertEqual(outside.read_bytes(), b'game data')
            handle = session(10, str(saves/'slot.sav'), None)
            self.assertGreater(handle, 0)
            self.assertEqual(session(11, handle, b'save data'), 9)
            self.assertEqual(session(4, handle, None), 9)
            self.assertEqual(session(12, handle, None), 0)
            session(1, handle, None)
            handle = session(0, str(saves/'slot.sav'), None)
            output = bytearray(9)
            self.assertEqual(session(2, handle, output), 9)
            self.assertEqual(output, b'save data')
            session.close()
            self.assertFalse(session.files)

    def test_directory_and_missing_path(self):
        session = backend_module.FileSession()
        with patch.object(backend_module.os, 'ilistdir',
                          return_value=iter([('room', 0x4000, 0, 0), ('data', 0x8000, 0, 12)]),
                          create=True):
            handle = session(7, '/quest/demo', None)
            self.assertEqual(session(8, handle, None), ('room', 0, True))
            self.assertEqual(session(8, handle, None), ('data', 12, False))
            self.assertIsNone(session(8, handle, None))
            session(9, handle, None)
            self.assertFalse(session.dirs)
        with patch.object(backend_module.os, 'stat', side_effect=OSError()):
            self.assertEqual(session(6, '/missing', None), 0)
        self.assertEqual(session.path('/quest/demo'), '/sd/scumm/demo')


class InputTests(unittest.TestCase):
    def setUp(self):
        self.tick = 0
        self.clock = SimpleNamespace(ticks_ms=lambda: self.tick,
            ticks_add=lambda a,b: (a+b) % (1<<30),
            ticks_diff=lambda a,b: ((a-b+(1<<29)) % (1<<30))-(1<<29))
        self.clock_patch = patch.object(backend_module, 'time', self.clock)
        self.clock_patch.start()
        control_patch=patch.dict(backend_module.MenuChord.poll.__globals__, {'time':self.clock})
        control_patch.start()
        self.addCleanup(control_patch.stop)
        self.addCleanup(self.clock_patch.stop)
        self.touch = SimpleNamespace(state=False, x=0, y=0, poll=lambda: None)
        self.backend = backend_module.Backend(SimpleNamespace(touch=self.touch), zoom=False)

    def test_deferred_save_write_pauses_audio_until_file_close(self):
        audio = SimpleNamespace(suspended=False)
        audio.pause = lambda: setattr(audio, 'suspended', True)
        self.backend.audio = audio
        class Files:
            def __init__(self):self.writes={}
            def __call__(self, op, a, b):
                if op==10:self.writes[1]='save'
                if op==1:self.writes.clear()
                return 1
        self.backend.files=Files()
        self.backend(10,'save',None)
        self.assertTrue(audio.suspended)
        self.backend(11,1,b'data')
        self.assertTrue(audio.suspended)
        self.backend(1,1,None)
        self.assertFalse(audio.suspended)
        audio.suspended=True  # saving while the menu still owns the pause
        self.backend(10,'save',None)
        self.backend(1,1,None)
        self.assertTrue(audio.suspended)

    def test_save_write_uses_boot_clock_and_menu_save_keeps_it(self):
        events = []
        clock = SimpleNamespace(active=True)
        def pause():
            clock.active = False
            events.append('boot')
        def resume():
            clock.active = True
            events.append('turbo')
        clock.pause, clock.resume = pause, resume
        self.backend.clock = clock
        class Files:
            def __init__(self):self.writes={}
            def __call__(self, op, a, b):
                if op==10:self.writes[1]='save'
                if op==11:events.append('write at '+('turbo' if clock.active else 'boot'))
                if op==1:self.writes.clear()
                return 1
        self.backend.files=Files()
        self.backend(10,'save',None)
        self.backend(11,1,b'data')
        self.backend(1,1,None)
        self.assertEqual(events, ['boot', 'write at boot', 'turbo'])
        clock.active = False  # menu save: the menu already chose the boot clock
        events.clear()
        self.backend(10,'save',None)
        self.backend(1,1,None)
        self.assertFalse(clock.active)
        self.assertNotIn('turbo', events)

    def test_menu_silences_audio_restores_palette_and_resumes_only_on_continue(self):
        for action in ('resume', 'saved', 'loaded', 'exit', 'restart', 'error'):
            with self.subTest(action=action):
                audio = SimpleNamespace(suspended=False, volume=60)
                audio.pause = lambda: setattr(audio, 'suspended', True)
                self.backend.audio = audio
                self.backend.path = '/game'
                picture = bytearray(b'pixels')
                shown = []
                self.backend.presto.display = picture
                self.backend.presto.palette_dirty = False
                def update():
                    self.assertTrue(audio.suspended)
                    self.assertTrue(self.backend.presto.palette_dirty)
                    self.assertEqual(picture, b'pixels')
                    shown.append(True)
                self.backend.presto.update = update
                def menu(title, zoom, slots, set_zoom, supplied_audio, set_volume):
                    self.assertTrue(audio.suspended)
                    self.assertIs(supplied_audio, audio)
                    picture[:] = b'menu!!'
                    if action == 'error':
                        raise RuntimeError('menu failed')
                    return action, zoom
                self.backend.ui = SimpleNamespace(pause=menu)
                with patch.dict('sys.modules', {'game_ui': SimpleNamespace(GameUI=object)}):
                    if action == 'error':
                        with self.assertRaisesRegex(RuntimeError, 'menu failed'):
                            self.backend.pause_menu()
                    else:
                        self.backend.pause_menu()
                self.assertTrue(shown)
                self.assertEqual(audio.suspended, action not in ('resume', 'saved', 'loaded'))

    def test_zoom_touch_coordinates_without_select_toggle(self):
        changed=[]
        self.backend.zoom_fn=changed.append
        self.backend.pad.buttons=4
        self.backend.zoom=True
        self.touch.state,self.touch.x,self.touch.y=True,479,389
        self.assertEqual(self.backend.event(),(3,319,199))
        self.assertEqual(changed,[])
        self.assertEqual(self.backend.event(),(4,319,199))
        self.tick=20
        self.assertIsNone(self.backend.event())
        self.assertEqual(changed,[])

    def test_touch_maps_to_game_and_releases_outside(self):
        self.touch.state, self.touch.x, self.touch.y = True, 100, 170
        self.assertEqual(self.backend.event(), (3, 20, 30))
        self.assertEqual(self.backend.event(), (4, 20, 30))
        self.tick = 20
        self.touch.x = 10
        self.assertEqual(self.backend.event(), (5, 20, 30))

    def test_pad_disconnect_releases_click_and_menu_chord_has_no_extra_keys(self):
        self.backend.pad.buttons = 1
        self.assertEqual(self.backend.event(), (4, 160, 100))
        self.tick = 20
        self.backend.pad.buttons = 0
        self.assertEqual(self.backend.event(), (5, 160, 100))
        self.tick = 40
        self.backend.path = '/game'
        menus=[]
        self.backend.pause_menu=lambda:menus.append(True)
        self.backend.pad.buttons = 4 | 8
        self.assertIsNone(self.backend.event())
        self.tick = 60
        self.assertIsNone(self.backend.event())
        self.assertEqual(menus,[True])
        self.assertFalse(self.backend.events)

    def test_old_xy_chord_is_only_individual_scumm_keys(self):
        self.backend.pad.buttons = 256 | 512
        self.assertEqual(self.backend.event(), (1,27,27))
        self.assertEqual(self.backend.event(), (1,32,32))
        self.assertFalse(self.backend.quit_sent)

    def test_wrapping_clock(self):
        self.backend.last_tick = (1<<30)-5
        self.tick = 7
        self.assertEqual(self.backend.now(), 12)

    def test_border_opens_same_menu_only_on_press_edge(self):
        menus=[]
        self.backend.path='/game'
        self.backend.pause_menu=lambda:menus.append(True)
        self.touch.state,self.touch.x,self.touch.y=True,450,20
        self.assertIsNone(self.backend.event())
        self.tick=20
        self.assertIsNone(self.backend.event())
        self.assertEqual(menus,[True])



class MenuTests(unittest.TestCase):
    def menu(self, pad_steps, touch_steps):
        class MenuPad:
            def __init__(self):
                self.pressed = self.actions = 0
                self.steps = iter(pad_steps)
            def poll(self):
                held, self.pressed, self.actions = next(self.steps)
                return held
        class Touch:
            def __init__(self):
                self.steps = iter(touch_steps)
            def poll(self):
                self.state, self.x, self.y = next(self.steps)
        class Canvas:
            def __init__(self, *args, **kwargs):
                pass
            def __getattr__(self, name):
                return lambda *args, **kwargs: 0
        presented = []
        presto = SimpleNamespace(touch=Touch(), presto=SimpleNamespace(update=presented.append))
        graphics = SimpleNamespace(PicoGraphics=Canvas, DISPLAY_PRESTO_FULL_RES=0, PEN_RGB565=0)
        with patch.dict('sys.modules', {'picographics': graphics}), \
                patch.object(backend_module, 'Gamepad', MenuPad), \
                patch.object(backend_module.time, 'sleep_ms', lambda n: None, create=True):
            result = backend_module.choose_on_screen(presto, backend_module.GAMES)
        return result, len(presented)

    def test_navigation_selects_mi1_and_only_redraws_changes(self):
        result, redraws = self.menu([(0,0,0),(128,128,128),(0,0,0),(1,1,1)],
                                   [(False,0,0)]*4)
        self.assertEqual(result, ('/sd/scumm/monkey-vga-de', 1))
        self.assertEqual(redraws, 2)

    def test_held_launch_button_must_be_released(self):
        result, _ = self.menu([(1,1,1),(0,0,0),(1,1,1)], [(False,0,0)]*3)
        self.assertEqual(result, ('/sd/scumm/monkey2-de', 2))

    def test_touch_gap_does_not_launch_and_next_row_does(self):
        result, _ = self.menu([(0,0,0)]*4,
            [(False,0,0),(True,30,175),(False,0,0),(True,30,200)])
        self.assertEqual(result, ('/sd/scumm/monkey-vga-de', 1))

    def test_touch_exit(self):
        result, _ = self.menu([(0,0,0)]*2, [(False,0,0),(True,30,430)])
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
