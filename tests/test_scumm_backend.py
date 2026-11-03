import importlib.util
from pathlib import Path
import tempfile
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
                               'scumm_files': files}):
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
        self.addCleanup(self.clock_patch.stop)
        self.touch = SimpleNamespace(state=False, x=0, y=0, poll=lambda: None)
        self.backend = backend_module.Backend(SimpleNamespace(touch=self.touch), zoom=False)

    def test_zoom_touch_coordinates_and_toggle(self):
        changed=[]
        self.backend.zoom_fn=changed.append
        self.backend.pad.buttons=4
        self.touch.state,self.touch.x,self.touch.y=True,479,389
        self.assertEqual(self.backend.event(),(3,319,199))
        self.assertEqual(changed,[True])
        self.assertEqual(self.backend.event(),(4,319,199))
        self.tick=20
        self.assertIsNone(self.backend.event())
        self.assertEqual(changed,[True])

    def test_touch_maps_to_game_and_releases_outside(self):
        self.touch.state, self.touch.x, self.touch.y = True, 100, 170
        self.assertEqual(self.backend.event(), (3, 20, 30))
        self.assertEqual(self.backend.event(), (4, 20, 30))
        self.tick = 20
        self.touch.x = 10
        self.assertEqual(self.backend.event(), (5, 20, 30))

    def test_pad_disconnect_releases_click_and_exit_chord_has_no_extra_keys(self):
        self.backend.pad.buttons = 1
        self.assertEqual(self.backend.event(), (4, 160, 100))
        self.tick = 20
        self.backend.pad.buttons = 0
        self.assertEqual(self.backend.event(), (5, 160, 100))
        self.tick = 40
        self.backend.pad.buttons = 256 | 512
        self.assertEqual(self.backend.event(), (10, 0, 0))
        self.tick = 60
        self.assertIsNone(self.backend.event())
        self.assertFalse(self.backend.events)

    def test_wrapping_clock(self):
        self.backend.last_tick = (1<<30)-5
        self.tick = 7
        self.assertEqual(self.backend.now(), 12)

    def test_border_controls_are_press_edges(self):
        changed=[]
        self.backend.zoom_fn=changed.append
        self.touch.state,self.touch.x,self.touch.y=True,450,20
        self.assertIsNone(self.backend.event())
        self.tick=20
        self.assertIsNone(self.backend.event())
        self.assertEqual(changed,[True])
        self.touch.state=False
        self.tick=40
        self.backend.event()
        self.touch.state,self.touch.x=True,20
        self.tick=60
        self.assertEqual(self.backend.event(),(10,0,0))


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
