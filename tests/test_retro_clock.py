import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest


def load_clock(machine):
    spec = importlib.util.spec_from_file_location('retro_clock_test',
        Path(__file__).resolve().parents[1] / 'device/lib/retro_clock.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', {'machine': machine}):
        spec.loader.exec_module(module)
    return module.EmulationClock


class ClockTests(unittest.TestCase):
    def test_restore_and_no_redundant_changes(self):
        hz = [200000000]
        calls = []
        def freq(value=None):
            if value is not None:
                hz[0] = value
                calls.append(value)
            return hz[0]
        clock = load_clock(SimpleNamespace(freq=freq))()
        clock.resume(); clock.resume()
        self.assertEqual(hz[0], clock.target)
        clock.pause(); clock.pause()
        self.assertEqual(hz[0], 200000000)
        self.assertEqual(calls, [clock.target, 200000000])

    def test_unsupported_clock_falls_back_once(self):
        calls = []
        def freq(value=None):
            if value is not None:
                calls.append(value)
                if value != 200000000:
                    raise ValueError('unsupported')
            return 200000000
        clock = load_clock(SimpleNamespace(freq=freq))()
        clock.resume(); clock.resume(); clock.pause()
        self.assertFalse(clock.active)
        self.assertEqual(clock.target, 200000000)
        self.assertEqual(len(calls), 2)
