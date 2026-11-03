import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

PERIOD = 1 << 30
class Bus:
    present = True
    proximity = 60
    channel = 100
    status = 5
    reads = 0
    identity = b'\x92\x05'
    def readfrom_mem(self, addr, reg, size):
        self.reads += 1
        if not self.present: raise OSError()
        return self.identity if reg == 0x86 else bytes((self.status,))
    def writeto_mem(self, *args):
        if not self.present: raise OSError()
    def readfrom_mem_into(self, addr, reg, data):
        if not self.present: raise OSError()
        data[:] = bytes((0,0,self.channel & 255,self.channel >> 8,0,
                         self.proximity & 255,self.proximity >> 8))

class AmbientTests(unittest.TestCase):
    def setUp(self):
        clock=SimpleNamespace(ticks_ms=lambda:0,
            ticks_add=lambda a,b:(a+b)%PERIOD,
            ticks_diff=lambda a,b:(a-b+PERIOD//2)%PERIOD-PERIOD//2)
        spec=importlib.util.spec_from_file_location('ambient_test',Path(__file__).resolve().parents[1]/'device/lib/ambient_sensor.py')
        self.mod=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules',{'machine':SimpleNamespace(I2C=None,Pin=None),'time':clock}):
            spec.loader.exec_module(self.mod)
        self.bus=Bus(); self.sensor=self.mod.AmbientSensor(self.bus)

    def test_absent_retries_and_reconnects(self):
        s=self.sensor; self.bus.present=False
        s.poll(0)
        for t in range(20,2000,20): s.poll(t)
        self.assertEqual(self.bus.reads,1)
        self.assertFalse(s.connected)
        self.assertEqual(s.brightness(25),1)
        self.bus.present=True; s.poll(2000); s.poll(2200)
        self.assertTrue(s.connected)
        self.assertIsNotNone(s.lux)
        self.bus.present=False; s.poll(2300)
        self.assertFalse(s.connected)
        self.assertIsNone(s.lux)
        self.assertEqual(s.target,1)

    def test_wrong_device_is_ignored(self):
        self.bus.identity=b'\xff\xff'; self.sensor.poll(0)
        self.assertFalse(self.sensor.connected)

    def test_debounce_cover_reveal_and_cooldown(self):
        s=self.sensor; s.poll(0); s.poll(200)
        self.bus.proximity=800
        self.assertEqual(s.poll(300),0)
        self.assertEqual(s.poll(400),self.mod.HELLO)
        self.assertEqual(s.poll(1200),0)
        self.assertEqual(s.poll(1300),self.mod.COVER)
        self.assertEqual(s.poll(1400),0)
        self.bus.proximity=60
        self.assertEqual(s.poll(1500),self.mod.REVEAL)
        self.bus.proximity=800
        s.poll(1600)
        self.assertEqual(s.poll(1700),0)

    def test_darkness_alone_does_not_trigger_and_fades_safely(self):
        s=self.sensor; self.bus.channel=0; s.poll(0)
        for t in range(200,2200,100): self.assertEqual(s.poll(t),0)
        self.assertFalse(s.covered)
        self.assertEqual(s.target,0.2)
        first=s.brightness(25)
        self.assertGreater(first,0.99)
        for i in range(200): s.brightness(25)
        self.assertAlmostEqual(s.level,0.2)
        self.bus.present=False; s.poll(2300)
        for i in range(200): s.brightness(25)
        self.assertAlmostEqual(s.level,1)

    def test_ticks_wrap_and_stale_light(self):
        s=self.sensor; s.next_poll=PERIOD-300
        s.poll(PERIOD-300); s.poll(PERIOD-100)
        self.bus.proximity=800
        s.poll(0); self.assertEqual(s.poll(100),self.mod.HELLO)
        self.assertEqual(s.poll(1000),self.mod.COVER)
        self.bus.status=1
        s.poll(4200)
        self.assertEqual(s.target,1)

class AmbientSceneTests(unittest.TestCase):
    def environment(self, event, busy=False, night=False):
        from test_gamepad import functions
        calls=[]
        class Lantern:
            def __init__(self,now,m,c):
                self.m, self.c = m,c
                calls.append('lantern')
        m=SimpleNamespace(state='idle',start=lambda state:calls.append(('m',state)))
        c=SimpleNamespace(state='idle',start=lambda state:calls.append(('c',state)))
        env=dict(ambient=SimpleNamespace(poll=lambda now:event,brightness=lambda dt:1,
                 connected=True,covered=event==2),lantern=None, ambient_search_seen=False,backlight_shown=1,presto=SimpleNamespace(set_backlight=lambda x:None),
                 leds=SimpleNamespace(),messy=m,clawd=c,director=None,Lantern=Lantern,
                 reminder=SimpleNamespace(active=lambda:False),
                 messy_wanted=lambda now:busy,clawd_wanted=lambda now:False,
                 seasons=SimpleNamespace(bedtime=lambda now:night),view='scene',
                 SENSOR_FREE=('idle','happy','wave'),HELLO=1,COVER=2)
        functions('device/desk/main.py',('handle_ambient',),env)
        return env,calls

    def test_greeting_does_not_trigger_but_cover_does_even_at_night(self):
        env,calls=self.environment(1)
        env['handle_ambient'](0,25)
        self.assertEqual(calls,[])
        for busy,night in ((False,True),):
            env,calls=self.environment(2,busy,night)
            env['handle_ambient'](0,25)
            self.assertEqual(calls,['lantern'])
        env,calls=self.environment(2)
        env['handle_ambient'](0,25)
        self.assertEqual(calls,['lantern'])

    def test_guybrush_lights_busy_actors_without_changing_them(self):
        env,calls=self.environment(2,busy=True)
        env['clawd_wanted']=lambda now:True
        env['handle_ambient'](0,25)
        self.assertEqual(calls,['lantern'])
        self.assertIsNone(env['director'])
        self.assertIs(env['lantern'].m,env['messy'])
        self.assertIs(env['lantern'].c,env['clawd'])
        env['lantern']=None
        calls.clear()
        env['handle_ambient'](100,25)
        self.assertEqual(calls,[])
        env['ambient'].covered=False
        env['handle_ambient'](200,25)
        env['ambient'].covered=True
        env['handle_ambient'](300,25)
        self.assertEqual(calls,['lantern'])

    def test_missing_sensor_blocks_but_other_activity_does_not(self):
        env,calls=self.environment(2)
        env['ambient'].connected=False
        env['handle_ambient'](0,25)
        self.assertEqual(calls,[])
        env['ambient'].connected=True
        env['reminder'].active=lambda:True
        env['director']=object()
        env['handle_ambient'](100,25)
        self.assertEqual(calls,['lantern'])

    def test_other_pages_still_block_sensor_visit(self):
        env,calls=self.environment(2,night=True)
        env['view']='home'
        env['handle_ambient'](0,25)
        self.assertEqual(calls,[])
