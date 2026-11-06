import struct
import unittest
from types import SimpleNamespace
from test_climate_darkness import module, PERIOD
from test_gamepad import functions, ROOT
import importlib.util
from unittest.mock import patch
from test_climate_darkness import CLOCK


class Bus:
    def __init__(self):
        self.present = True
        self.address = 0x6a
        self.identity = 0x6a
        self.status = 3
        self.tap = 0
        self.values = (0, 0, 0, 0, 0, 16384)
        self.reads = 0
        self.writes = []

    def readfrom_mem(self, address, register, count):
        self.reads += 1
        if not self.present or address != self.address:
            raise OSError()
        if register == 0x0f:
            return bytes((self.identity,))
        if register == 0x1e:
            return bytes((self.status,))
        if register == 0x1c:
            result, self.tap = self.tap, 0
            return bytes((result,))
        raise AssertionError(register)

    def writeto_mem(self, address, register, data):
        self.writes.append((register, data[0]))

    def readfrom_mem_into(self, address, register, buf):
        if not self.present:
            raise OSError()
        assert register == 0x22
        buf[:] = struct.pack('<hhhhhh', *self.values)


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.mod = module('motion_sensor')
        self.bus = Bus()
        self.sensor = self.mod.MotionSensor(self.bus)
        self.sensor.poll(0)

    def calibrate(self):
        for t in range(100, 1000, 30):
            self.assertEqual(self.sensor.poll(t), 0)
        self.assertTrue(self.sensor.ready)

    def test_rest_boot_and_signed_tilt(self):
        self.calibrate()
        self.assertEqual(self.sensor.tilt, 0)
        self.bus.values = (0, 0, 0, -9000, 0, 14000)
        for t in range(1000, 1400, 30): self.sensor.poll(t)
        self.assertLess(self.sensor.tilt, -0.5)
        self.assertEqual(self.sensor.gyro, [0, 0, 0])

    def test_tap_shake_and_cooldown(self):
        self.calibrate()
        self.bus.tap = 0x20
        self.assertEqual(self.sensor.poll(1000), self.mod.TAP)
        self.bus.tap = 0x20
        self.assertEqual(self.sensor.poll(1030), 0)
        self.bus.values = (20000, 0, 0, 0, 0, 16384)
        self.assertEqual(self.sensor.poll(3100), 0)
        self.assertEqual(self.sensor.poll(3130), self.mod.SHAKE)
        self.assertEqual(self.sensor.poll(3160), 0)
        self.assertEqual(self.sensor.poll(3190), 0)

    def test_missing_wrong_identity_and_alternate_address(self):
        self.bus.present = False
        self.sensor.poll(100)
        self.assertFalse(self.sensor.connected)
        reads = self.bus.reads
        self.sensor.poll(1000)
        self.assertEqual(self.bus.reads, reads)
        self.bus.present = True
        self.bus.identity = 0
        self.sensor.poll(2100)
        self.assertFalse(self.sensor.connected)
        self.bus.identity = 0x6a
        self.bus.address = 0x6b
        self.sensor.poll(4100)
        self.assertTrue(self.sensor.connected)
        self.assertEqual(self.sensor.address, 0x6b)
        self.assertFalse(self.sensor.ready)

    def test_stale_and_disconnect_clear_animation_data(self):
        self.calibrate()
        self.sensor.tilt = 1
        self.bus.status = 0
        self.sensor.poll(2100)
        self.assertFalse(self.sensor.connected)
        self.assertFalse(self.sensor.ready)
        self.assertEqual(self.sensor.tilt, 0)

    def test_moving_boot_waits_for_rest(self):
        self.bus.values = (20000, 0, 0, 0, 0, 16384)
        for t in range(100, 1200, 30): self.sensor.poll(t)
        self.assertFalse(self.sensor.ready)
        self.bus.values = (0, 0, 0, 0, 0, 16384)
        for t in range(1300, 2300, 30): self.sensor.poll(t)
        self.assertTrue(self.sensor.ready)

    def test_clock_wrap(self):
        self.calibrate()
        self.sensor.next_poll = PERIOD-100
        self.bus.tap = 0x20
        self.assertEqual(self.sensor.poll(PERIOD-100), self.mod.TAP)
        self.bus.tap = 0x20
        self.assertEqual(self.sensor.poll(100), 0)
        self.bus.tap = 0x20
        self.assertEqual(self.sensor.poll(2100), self.mod.TAP)


class ReactionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('reaction', ROOT/'device/desk/scene/motion.py')
        self.mod = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {'time': CLOCK, 'motion_sensor': module('motion_sensor')}):
            spec.loader.exec_module(self.mod)

    def test_blocked_events_are_discarded_and_pose_does_not_move_actors(self):
        reaction = self.mod.MotionReaction()
        reaction.update(0, 2, False)
        self.assertEqual(reaction.kind, 0)
        reaction.update(100, 0, True)
        self.assertEqual(reaction.kind, 0)
        reaction.update(200, 2, True)
        hp, cp = SimpleNamespace(), SimpleNamespace()
        reaction.apply(350, 0, hp, cp)
        self.assertEqual((hp.dx, cp.dx), (-10, 10))
        reaction.update(6300, 0, True)
        self.assertEqual(reaction.kind, 0)
        reaction.apply(6400, -0.8, hp, cp)
        self.assertEqual((hp.dx, cp.dx), (-8, -8))
        reaction.update(6500, 1, True)
        reaction.apply(6500, 0, hp, cp)
        self.assertEqual((hp.look, cp.look), (0, 0))
        reaction.update(3500, 0, False)
        self.assertEqual(reaction.kind, 0)

    def test_scene_gate_allows_night_work_and_all_activities(self):
        env = dict(motion=SimpleNamespace(ready=True), view='scene',
                   seasons=SimpleNamespace(bedtime=lambda now:False),
                   director=None, lantern=None, reminder=SimpleNamespace(active=lambda:False),
                   messy=SimpleNamespace(state='idle'), clawd=SimpleNamespace(state='idle'),
                   messy_wanted=lambda now:None, clawd_wanted=lambda now:None)
        functions('device/desk/main.py', ('motion_allowed',), env)
        self.assertTrue(env['motion_allowed'](0))
        for state in ('sleep', 'work', 'wheel', 'broken', 'ball', 'duo', 'walk'):
            env['messy'].state = state
            self.assertTrue(env['motion_allowed'](0))
        env['messy'].state = 'idle'
        for key in ('director', 'lantern'):
            env[key] = object()
            self.assertTrue(env['motion_allowed'](0))
            env[key] = None
        env['seasons'].bedtime = lambda now:True
        self.assertTrue(env['motion_allowed'](0))
        env['seasons'].bedtime = lambda now:False
        env['clawd_wanted'] = lambda now:'work'
        self.assertTrue(env['motion_allowed'](0))

        env['view'] = 'apps'
        self.assertFalse(env['motion_allowed'](0))
        env['view'] = 'scene'
        env['motion'].ready = False
        self.assertFalse(env['motion_allowed'](0))

    def test_sleep_wakes_longer_and_held_tilt_does_not_keep_awake(self):
        reaction = self.mod.MotionReaction()
        hp, cp = SimpleNamespace(eyes='closed'), SimpleNamespace(eyes='closed')
        reaction.update(0, 0, True, 0.8)
        self.assertTrue(reaction.waking(4000))
        reaction.apply(4000, 0.8, hp, cp, (True, True))
        self.assertEqual((hp.eyes, cp.eyes), ('wide', 'wide'))  # awake and leaning
        reaction.update(6100, 0, True, 0.8)
        self.assertFalse(reaction.waking(6100))
        hp.eyes = cp.eyes = 'closed'
        reaction.apply(6100, 0.8, hp, cp, (True, True))
        self.assertEqual((hp.eyes, cp.eyes), ('closed', 'closed'))
        reaction.update(6200, 1, True, 0.8)
        self.assertTrue(reaction.waking(6200))
        reaction.update(12300, 0, True, 0.8)
        self.assertFalse(reaction.waking(12300))
        reaction.update(12400, 0, True, 0)
        reaction.update(12500, 0, True, -0.8)
        self.assertTrue(reaction.waking(12500))

    def test_returning_stick_to_rest_keeps_sleepers_awake_for_six_seconds(self):
        reaction = self.mod.MotionReaction()
        reaction.update(0, 0, True, 0.8)
        reaction.update(500, 0, True, 0)
        self.assertTrue(reaction.waking(4000))
        hp, cp = SimpleNamespace(eyes='closed'), SimpleNamespace(eyes='closed')
        reaction.apply(4000, 0, hp, cp, (True, True))
        self.assertEqual((hp.eyes, cp.eyes), ('open', 'open'))
        self.assertFalse(reaction.waking(6000))

    def test_wake_timer_wraps_and_reaction_reveals_hidden_pose(self):
        reaction = self.mod.MotionReaction()
        reaction.update(PERIOD-500, 0, True, 0.8)
        self.assertTrue(reaction.waking(500))
        self.assertFalse(reaction.waking(5600))
        hp = SimpleNamespace(hide=True, sink=28, eyes='closed', laptop=True)
        cp = SimpleNamespace(hide=True, sink=10, eyes='down', laptop=True)
        reaction.update(1000, 2, True)
        reaction.apply(1100, 0, hp, cp)
        self.assertFalse(hp.hide or cp.hide)
        self.assertEqual((hp.sink, cp.sink), (0, 0))
        self.assertTrue(cp.laptop)  # status props survive the overlay

    def test_shake_moves_then_settles_and_tap_looks_both_ways(self):
        reaction = self.mod.MotionReaction()
        reaction.update(0, 2, True)
        poses = []
        for t in (150, 300, 600, 1800, 3000, 5900):
            hp, cp = SimpleNamespace(), SimpleNamespace()
            reaction.apply(t, 0, hp, cp)
            poses.append((hp.dx, getattr(hp, 'jump', 0), hp.eyes))
        self.assertEqual(poses[1][:2], (-20, 12))  # thrown about
        self.assertEqual(poses[4][1], 0)  # dizzy on the ground
        self.assertLessEqual(abs(poses[-1][0]), 2)  # and settling
        reaction.update(6100, 0, True)
        self.assertEqual(reaction.kind, 0)
        reaction.update(6200, 1, True)
        reaction.apply(7100, 0, hp, cp)
        self.assertEqual(hp.look, -1)
        reaction.apply(8000, 0, hp, cp)
        self.assertEqual(hp.look, 1)
        reaction.update(11300, 0, True)
        self.assertEqual(reaction.kind, 0)
