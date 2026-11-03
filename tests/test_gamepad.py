"""Hardware-free checks for optional input and disconnect behavior."""
import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parents[1]
PERIOD = 1 << 30


class Clock:
    now = 0

    def ticks_ms(self):
        return self.now

    def ticks_add(self, a, b):
        return (a + b) % PERIOD

    def ticks_diff(self, a, b):
        return (a - b + PERIOD // 2) % PERIOD - PERIOD // 2


class Bus:
    def __init__(self, address=0x21):
        self.address = address
        self.present = True
        self.raw = 0xffff
        self.reads = 0

    def readfrom_mem_into(self, address, register, buffer):
        self.reads += 1
        if not self.present or address != self.address:
            raise OSError('Disconnected')
        buffer[0], buffer[1] = self.raw & 255, self.raw >> 8

    def writeto_mem(self, address, register, value):
        if not self.present:
            raise OSError('Disconnected')


def functions(path, names, env):
    tree = ast.parse((ROOT / path).read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(tree, path, 'exec'), env)


class GamepadTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.bus = Clock(), Bus()
        spec = importlib.util.spec_from_file_location('test_pad', ROOT / 'device/lib/gamepad.py')
        self.mod = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'machine': SimpleNamespace(), 'time': self.clock}):
            spec.loader.exec_module(self.mod)
        self.pad = self.mod.Gamepad(self.bus)

    def test_every_physical_button_and_simultaneous_buttons(self):
        for bit, button in self.mod.BUTTONS:
            self.bus.raw = 0xffff & ~(1 << bit)
            self.clock.now += 16
            self.assertEqual(self.pad.poll(self.clock.now), button)
        self.bus.raw = 0xffff & ~((1 << 14) | (1 << 3))
        self.assertEqual(self.pad.poll(self.clock.now + 16), self.mod.A | self.mod.RIGHT)

    def test_edges_repeat_and_release(self):
        self.bus.raw &= ~(1 << 1)
        self.pad.poll(0)
        self.assertEqual(self.pad.pressed, self.mod.UP)
        self.pad.poll(16)
        self.assertEqual(self.pad.actions, 0)
        self.pad.poll(400)
        self.assertEqual(self.pad.actions, self.mod.UP)
        self.assertEqual(self.pad.pressed, 0)
        self.bus.raw = 0xffff
        self.assertEqual(self.pad.poll(416), 0)
        self.assertEqual(self.pad.actions, 0)

    def test_disconnect_releases_keys_and_reconnects(self):
        self.bus.raw &= ~(1 << 14)
        self.assertEqual(self.pad.poll(0), self.mod.A)
        self.bus.present = False
        self.assertEqual(self.pad.poll(16), 0)
        self.assertFalse(self.pad.connected)
        self.assertEqual(self.pad.pressed | self.pad.actions, 0)
        reads = self.bus.reads
        self.pad.poll(500)
        self.assertEqual(self.bus.reads, reads)
        self.bus.present = True
        self.bus.raw = 0xffff
        self.assertEqual(self.pad.poll(1016), 0)
        self.assertTrue(self.pad.connected)

    def test_missing_pad_does_not_probe_every_frame(self):
        self.bus.present = False
        for now in range(0, 1000, 16):
            self.assertEqual(self.pad.poll(now), 0)
        self.assertEqual(self.bus.reads, 4)
        self.assertFalse(self.pad.connected)

    def test_sensor_at_23_is_not_mistaken_for_gamepad(self):
        self.bus.address = 0x23
        original = self.bus.readfrom_mem_into
        def read(address, register, buffer):
            original(address, register, buffer)
            if register == 0x86:
                buffer[0], buffer[1] = 0x92, 0x05
        self.bus.readfrom_mem_into = read
        self.bus.writeto_mem = lambda *args: self.fail('Sensor configured as a pad')
        self.pad.poll(0)
        self.assertFalse(self.pad.connected)
        self.assertEqual(self.pad.buttons, 0)

    def test_alternate_address(self):
        self.bus.address = 0x27
        self.pad.poll(0)
        self.assertEqual(self.pad.address, 0x27)

    def test_repeat_across_tick_wrap(self):
        start = PERIOD - 100
        self.clock.now = start
        self.pad = self.mod.Gamepad(self.bus)
        self.bus.raw &= ~(1 << 2)
        self.pad.poll(start)
        self.pad.poll(self.clock.ticks_add(start, 400))
        self.assertEqual(self.pad.actions, self.mod.LEFT)

    def test_menu_navigation_and_selection(self):
        toggles, launches, pokes = [], [], []
        pages = SimpleNamespace(VIEWS=('scene', 'today', 'agents', 'pipelines', 'home', 'settings', 'apps'),
                                SETTING_ROWS=range(5), SETTING_Y0=32, SETTING_H=38, APP_COLS=3,
                                app_slot=lambda i: (i % 3 * 80, i // 3 * 48), pad_focus=None,
                                tap_settings=lambda x, y: toggles.append(y),
                                tap_apps=lambda x, y, now: launches.append((x, y)))
        pad = SimpleNamespace(poll=lambda now: None, connected=True, actions=0, pressed=0)
        env = {k: getattr(self.mod, k) for k in ('A', 'B', 'DOWN', 'LEFT', 'RIGHT', 'SELECT', 'START', 'UP', 'X', 'Y')}
        env.update(pages=pages, pad=pad, pad_app=0, pad_setting=0, view='scene', WIDTH=240,
                   sound=SimpleNamespace(stop_music=lambda: None), poke=lambda p, now: pokes.append(p))
        functions('device/desk/main.py', ('change_view', 'handle_gamepad'), env)

        def press(button):
            pad.pressed = pad.actions = button
            env['handle_gamepad'](100)

        press(self.mod.START)
        self.assertEqual(env['view'], 'today')
        env['change_view']('settings')
        press(self.mod.DOWN)
        press(self.mod.A)
        self.assertEqual(toggles, [70])
        self.assertEqual(pages.pad_focus, ('settings', 1))
        with patch.dict(sys.modules, {'desk': SimpleNamespace(apps=SimpleNamespace(get=lambda: range(12)))}):
            press(self.mod.Y)
            press(self.mod.DOWN)
            press(self.mod.RIGHT)
            press(self.mod.A)
        self.assertEqual(launches, [(81, 49)])
        press(self.mod.B)
        self.assertEqual(env['view'], 'scene')
        press(self.mod.A)
        self.assertEqual(pokes, [(0, 0)])
        pad.connected = False
        pad.actions = pad.pressed = 0
        env['handle_gamepad'](120)
        self.assertIsNone(pages.pad_focus)

    def test_touch_navigation_without_gamepad(self):
        taps = []
        touch = SimpleNamespace(poll=lambda: None, state=True, x=100, y=100)
        env = dict(touch=touch, was_touched=False, touch_start=None, touch_last=None,
                   view='scene', name_tag=None, poke=lambda p, now: taps.append(p),
                   sound=SimpleNamespace(stop_music=lambda: None),
                   pages=SimpleNamespace(VIEWS=('scene', 'today')))
        functions('device/desk/main.py', ('change_view', 'handle_touch'), env)
        env['handle_touch'](0)
        touch.state = False
        env['handle_touch'](20)
        self.assertEqual(taps[-1], (100, 100))
        touch.state = True
        env['handle_touch'](40)
        touch.x = 30
        env['handle_touch'](60)
        touch.state = False
        env['handle_touch'](80)
        self.assertEqual(env['view'], 'today')


class StopFrames(Exception):
    pass


class Reset(Exception):
    pass


class EmulatorInputTests(unittest.TestCase):
    def environment(self, states, touch_keys=0, frame_ms=20):
        frames, saves = [], []
        clock = Clock()
        clock.ticks_us = lambda: clock.now * 1000
        clock.sleep_us = lambda us: setattr(clock, "now", clock.now + (us + 999) // 1000)

        def frame(fb, keys, x, y, draw, fullscreen=False):
            self.assertEqual((x, y), (0, 0))
            if len(frames) >= len(states):
                raise StopFrames()
            self.assertEqual(env['cpu_hz'][0], 300000000)
            env['frame_modes'].append(fullscreen)
            env['frame_draws'].append(draw)
            frames.append(keys)
            clock.now += frame_ms(draw) if callable(frame_ms) else frame_ms

        def reset():
            raise Reset()

        from test_retro_clock import load_clock
        cpu_hz = [200000000]
        def freq(value=None):
            if value is not None:
                cpu_hz[0] = value
            return cpu_hz[0]
        def checked_save(ram, path):
            self.assertEqual(cpu_hz[0], 200000000)
            saves.append(path)
        machine = SimpleNamespace(reset=reset, freq=freq)
        env = dict(time=clock, machine=machine, EmulationClock=load_clock(machine), cpu_hz=cpu_hz,
                   pad=SimpleNamespace(connected=True, pressed=0, poll=lambda now=None: states[min(len(frames), len(states)-1)]),
                   gbcore=SimpleNamespace(init=lambda rom: 0, palette=lambda *args: None, frame=frame),
                   message=lambda *args: None, short_name=lambda path: path,
                   wait_for_pad=lambda: None, clear_game=lambda: None,
                   presto=SimpleNamespace(update=lambda: None), SHADES=(0, 1, 2, 3), fb=None,
                   hold_b=False, X=256, Y=512, JOYPAD_B=2, GX=4, GY=2,
                   X_X=208, X_Y=4, FRAME_US=16742, SAVE_EVERY_MS=30000,
                   fingers=lambda: ((10, 180),) if touch_keys else (),
                   keys_at=lambda x, y: touch_keys, toggle_at=lambda x, y: False,
                   save=checked_save, frame_modes=[], frame_draws=[])
        env['extension'] = lambda p: '.' + p.rsplit('.', 1)[-1].lower()
        env['read_rom'] = lambda p: b'rom'
        env['load_core'] = lambda p: (env['gbcore'], 16742)
        functions('device/lib/retro.py', ('run',), env)
        return env, frames, saves

    def test_fullscreen_uses_gamepad_only_and_releases_keys(self):
        env, frames, _ = self.environment([1 | 16, 0, 2], touch_keys=64)
        with patch('builtins.open', mock_open(read_data=b'rom')):
            with self.assertRaises(StopFrames):
                env['run']('test.gb')
        self.assertEqual(frames, [1 | 16, 0, 2])
        self.assertTrue(all(mode is True for mode in env['frame_modes']))

    def test_nes_defaults_large_and_y_toggles_integer_scale(self):
        env, frames, _ = self.environment([0, 0, 0])
        def poll(now=None):
            pressed = 512 if len(frames) in (0, 2) else 0
            env['pad'].pressed = pressed
            return pressed
        env['pad'].poll = poll
        with self.assertRaises(StopFrames):
            env['run']('test.nes')
        self.assertEqual(env['frame_modes'], [1, 1, 2])

    def test_exit_chord_does_not_toggle_zoom(self):
        env, frames, _ = self.environment([256 | 512] * 80)
        env['pad'].pressed = 256 | 512
        with self.assertRaises(Reset):
            env['run']('test.nes')
        self.assertTrue(all(mode == 2 for mode in env['frame_modes']))

    def test_nes_and_sms_keep_all_emulation_steps_but_draw_every_second(self):
        for suffix in ('.nes', '.sms'):
            env, frames, _ = self.environment([1, 2, 16, 32, 64, 128], frame_ms=5)
            env['gbcore'].init = lambda *args: 0
            with self.assertRaises(StopFrames):
                env['run']('test' + suffix)
            self.assertEqual(frames, [1, 2, 16, 32, 64, 128])
            self.assertEqual(env['frame_draws'], [True, False, True, False, True, False])

    def test_slow_rendering_skips_more_images_to_keep_game_speed(self):
        for suffix in ('.nes', '.sms'):
            inputs = [i & 255 for i in range(96)]
            env, frames, _ = self.environment(inputs,
                frame_ms=lambda draw: 30 if draw else 5)
            env['gbcore'].init = lambda *args: 0
            with self.assertRaises(StopFrames):
                env['run']('test' + suffix)
            self.assertEqual(frames, inputs)
            drawn = [i for i, draw in enumerate(env['frame_draws']) if draw]
            self.assertLess(len(drawn), len(inputs) // 2)
            self.assertTrue(all(b - a >= 2 for a, b in zip(drawn, drawn[1:])))
            self.assertLessEqual(env['time'].now, 96 * 16.742 + 30)

    def test_emulator_does_not_load_without_gamepad(self):
        env, frames, _ = self.environment([0, 0], touch_keys=1)
        env['pad'].connected = False
        env['touch'] = SimpleNamespace(poll=lambda: None, state=True)
        env['gbcore'].init = lambda rom: self.fail('ROM loaded without gamepad')
        functions('device/lib/retro.py', ('wait_for_pad', 'back_on_touch'), env)
        with patch('builtins.open', mock_open(read_data=b'rom')):
            with self.assertRaises(Reset):
                env['run']('test.gb')
        self.assertEqual(frames, [])

    def test_disconnect_saves_and_pauses_then_resumes(self):
        env, frames, saves = self.environment([1, 16, 0])
        inputs = iter((1, None, 16, 0, 0))
        pauses = []

        def poll(now=None):
            held = next(inputs)
            env['pad'].connected = held is not None
            return held or 0

        def wait():
            if not env['pad'].connected:
                self.assertEqual(env['cpu_hz'][0], 200000000)
                pauses.append(len(frames))
                env['pad'].connected = True

        env['pad'].poll = poll
        env['wait_for_pad'] = wait
        with patch('builtins.open', mock_open(read_data=b'rom')):
            with self.assertRaises(StopFrames):
                env['run']('test.gb')
        self.assertEqual(pauses, [1])
        self.assertEqual(saves, ['test.sav'])
        self.assertEqual(frames, [1, 16, 0])

    def test_autosave_uses_normal_clock_and_resumes(self):
        env, frames, saves = self.environment([0, 0, 0])
        env['gbcore'].init = lambda rom: 1
        env['gbcore'].set_ram = lambda ram: None
        env['SAVE_EVERY_MS'] = 1
        with patch('builtins.open', mock_open(read_data=b'0')):
            with self.assertRaises(StopFrames):
                env['run']('test.gb')
        self.assertTrue(saves)
        self.assertEqual(env['cpu_hz'][0], 200000000)

    def test_exception_restores_cpu_clock(self):
        env, frames, _ = self.environment([0])
        with self.assertRaises(StopFrames):
            env['run']('test.gb')
        self.assertEqual(env['cpu_hz'][0], 200000000)

    def test_exit_chord_saves_before_reset(self):
        env, frames, saves = self.environment([256 | 512] * 80)
        with patch('builtins.open', mock_open(read_data=b'rom')):
            with self.assertRaises(Reset):
                env['run']('test.gb')
        self.assertEqual(saves, ['test.sav'])
        self.assertTrue(all(keys == 0 for keys in frames))
        self.assertEqual(len(frames), 50)


if __name__ == '__main__':
    unittest.main()
