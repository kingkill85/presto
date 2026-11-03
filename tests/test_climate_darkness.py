import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import struct
import unittest

PERIOD = 1 << 30
CLOCK = SimpleNamespace(ticks_ms=lambda: 0, ticks_add=lambda a,b:(a+b)%PERIOD,
    ticks_diff=lambda a,b:(a-b+PERIOD//2)%PERIOD-PERIOD//2)

def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / ('device/lib/' + name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', {'time': CLOCK, 'machine': SimpleNamespace(I2C=None, Pin=None)}):
        spec.loader.exec_module(mod)
    return mod

class Bus:
    present = True
    busy = False
    identity = b'\x60'
    reads = 0
    def readfrom_mem(self, addr, reg, count):
        self.reads += 1
        if not self.present: raise OSError()
        if reg == 0xd0: return self.identity
        if reg == 0xf3: return bytes((9 if self.busy else 0,))
        if reg == 0x88:
            return struct.pack('<HhhHhhhhhhhhBB', 27504,26435,-1000,36477,-10685,3024,2855,140,-7,15500,-14600,6000,0,75)
        if reg == 0xe1: return struct.pack('<hBBBBb',362,0,20,0,3,30)
        raise AssertionError(reg)
    def writeto_mem(self, *args):
        if not self.present: raise OSError()
    def readfrom_mem_into(self, addr, reg, buf):
        if not self.present: raise OSError()
        buf[:] = (415148 << 4).to_bytes(3,'big') + (519888 << 4).to_bytes(3,'big') + (30000).to_bytes(2,'big')

class ClimateTests(unittest.TestCase):
    def setUp(self):
        self.mod = module('climate_sensor')
        self.bus = Bus()
        self.sensor = self.mod.ClimateSensor(self.bus)
    def sample(self, offset=0):
        for t in (0,10,11,31): self.sensor.poll((offset+t)%PERIOD)
    def test_datasheet_temperature_pressure_vector(self):
        self.sample()
        t,h,p = self.sensor.values
        self.assertEqual(t,25.1)
        self.assertEqual(p,1007)
        self.assertTrue(0 <= h <= 100)
    def test_disconnect_backoff_reconnect(self):
        self.sample()
        self.bus.present=False
        self.sensor.poll(5031)
        self.assertIsNone(self.sensor.values)
        reads=self.bus.reads
        for t in range(5032,7031): self.sensor.poll(t)
        self.assertEqual(self.bus.reads,reads)
        self.bus.present=True
        self.sample(7031)
        self.assertIsNotNone(self.sensor.values)
    def test_wrong_identity_and_stuck_measurement(self):
        self.bus.identity=b'\x58'
        self.sensor.poll(0)
        self.assertEqual(self.sensor.phase,'connect')
        self.bus.identity=b'\x60'
        for t in (2000,2010,2011): self.sensor.poll(t)
        self.bus.busy=True
        self.sensor.poll(2031)
        self.sensor.poll(2211)
        self.assertIsNone(self.sensor.values)
        self.assertEqual(self.sensor.phase,'connect')
    def test_wrap_and_signed_calibration(self):
        self.sensor.next_poll=PERIOD-20
        self.sample(PERIOD-20)
        self.assertIsNotNone(self.sensor.values)
        self.assertEqual(self.mod.signed(0xfff,12),-1)
        self.assertEqual(self.mod.signed(0x80,8),-128)

class DarknessTests(unittest.TestCase):
    def setUp(self):
        self.gate=module('darkness').Darkness()
        self.sensor=SimpleNamespace(connected=True,lux=1,light_at=0,near=False,proximity=0,baseline=60)
    def poll(self, t, allowed=True):
        self.sensor.light_at=t
        return self.gate.poll(t,self.sensor,allowed)
    def test_one_visit_until_bright_again_and_cooldown(self):
        self.assertFalse(self.poll(0))
        self.assertTrue(self.poll(2000))
        for t in (4000,6000,310000): self.assertFalse(self.poll(t))
        self.sensor.lux=10
        self.poll(312000);self.poll(314000)
        self.sensor.lux=1
        self.poll(316000)
        self.assertTrue(self.poll(318000))
        self.sensor.lux=10
        self.poll(320000);self.poll(322000)
        self.sensor.lux=1
        self.poll(324000)
        self.assertFalse(self.poll(326000))
    def test_cover_missing_and_stale_never_trigger(self):
        self.sensor.proximity=800
        self.poll(0)
        self.assertFalse(self.poll(2100))
        self.sensor.proximity=0
        self.poll(2200)
        self.sensor.connected=False
        self.assertFalse(self.poll(4300))
        self.sensor.connected=True
        self.poll(5000)
        self.assertFalse(self.gate.poll(9000,self.sensor,True))
    def test_deferred_visit_and_wrapping_clock(self):
        self.assertFalse(self.poll(PERIOD-1000,False))
        self.assertFalse(self.poll(1000,False))
        self.assertTrue(self.poll(1100,True))
