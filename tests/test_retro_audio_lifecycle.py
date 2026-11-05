"""Exercise the actual console loop without starting hardware entry points."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_gamepad import functions


class LifecycleTests(unittest.TestCase):
    def test_disconnect_menu_autosave_and_exception_stop_audio_before_clock(self):
        events = []
        state = {'audio': False, 'clock': False, 'poll': 0, 'ms': 0}
        class Done(Exception): pass
        class Clock:
            def resume(self):
                state['clock'] = True
                events.append('clock on')
            def pause(self):
                assert not state['audio']
                state['clock'] = False
                events.append('clock off')
        class Audio:
            def __init__(self, core, volume): self.volume = volume
            def resume(self):
                assert state['clock']
                state['audio'] = True
                events.append('audio on')
            def pause(self):
                state['audio'] = False
                events.append('audio off')
            def frame(self):
                assert state['clock'] and state['audio']
                events.append('audio frame')
        pad = SimpleNamespace(connected=True)
        def poll(now):
            state['poll'] += 1
            pad.connected = state['poll'] != 2
            return 12 if state['poll'] == 3 else 0
        pad.poll = poll
        def wait():
            assert not state['audio'] and not state['clock']
            pad.connected = True
        def save(*args):
            assert not state['audio'] and not state['clock']
            events.append('save')
        def menu(*args):
            assert not state['audio'] and not state['clock']
            events.append('menu')
            return 'loaded', True
        rams = []
        def frame(*args):
            if state['poll'] == 5: raise Done()
            state['ms'] += 100
            rams[0][0] += 1  # changed battery RAM is autosaved
        core = SimpleNamespace(init=lambda rom:4, set_ram=rams.append,
                               palette=lambda *a:None, frame=frame, audio=True)
        env = dict(gc=SimpleNamespace(collect=lambda:None), wait_for_pad=wait, message=lambda *a:None, short_name=lambda p:p,
                   read_rom=lambda p:bytearray(400), load_core=lambda p:(core,16743),
                   extension=lambda p:'.gb', SHADES=(0,1,2,3), zoom_for=lambda p:True,
                   system_for=lambda p:('GB',), StateSlots=lambda *a:None,
                   MenuChord=lambda:SimpleNamespace(poll=lambda held,now:(0,held==12)),
                   clear_game=lambda:None, EmulationClock=Clock, volume_for=lambda p:60,
                   pad=pad, ui=SimpleNamespace(pause=menu), fb=bytearray(4),
                   presto=SimpleNamespace(update=lambda:None), save=save, SAVE_EVERY_MS=30,
                   time=SimpleNamespace(ticks_ms=lambda:state['ms'], ticks_us=lambda:state['ms']*1000,
                                        ticks_add=lambda a,b:a+b,ticks_diff=lambda a,b:a-b,
                                        sleep_us=lambda n:None))
        functions('device/lib/retro.py', ['run'], env)
        with patch.dict(sys.modules, {'retro_audio':SimpleNamespace(Audio=Audio)}), \
             patch('builtins.open', side_effect=OSError):
            with self.assertRaises(Done): env['run']('/test.gb')
        self.assertIn('menu',events)
        self.assertGreaterEqual(events.count('save'),2)
        self.assertFalse(state['audio'])
        self.assertFalse(state['clock'])
        self.assertEqual(events[-2:],['audio off','clock off'])


class DMAReleaseTests(unittest.TestCase):
    def test_busy_stream_is_not_modified_or_claimed(self):
        from test_game_library import load
        registers = {0x400c8018: 12, 0x400c8008: 0}
        module = load('retro_audio', machine=SimpleNamespace(PWM=None, Pin=None, mem32=registers),
                      rp2=SimpleNamespace(DMA=None),
                      uctypes=SimpleNamespace(addressof=lambda b:0x11000000))
        audio = module.Audio(SimpleNamespace(audio_samples=369))
        with patch.dict(sys.modules, {'audiofifo':SimpleNamespace()}):
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                audio.resume()
        self.assertFalse(audio.stream_owned)
        self.assertEqual(registers, {0x400c8018:12, 0x400c8008:0})

    def test_stream_is_stopped_only_after_dma_abort_and_close(self):
        from test_game_library import load
        events = []
        class Registers(dict):
            def __setitem__(self, key, value):
                events.append(('register', key, value))
                super().__setitem__(key, value)
        class Channel:
            channel = 3
            def pack_ctrl(self, **kw): return kw
            def config(self, **kw): events.append('unlink')
            def active(self, value): events.append('abort')
            def close(self): events.append('close')
        registers = Registers({0x400c8008:2})
        module = load('retro_audio', machine=SimpleNamespace(PWM=None, Pin=None, mem32=registers),
                      rp2=SimpleNamespace(DMA=None), uctypes=SimpleNamespace(addressof=id))
        audio = module.Audio(SimpleNamespace(audio_samples=369))
        audio.channels = [Channel()]
        audio.stream_owned = True
        audio.stream_address = 0x11004000
        audio.pause()
        self.assertEqual(events, ['unlink', 'abort', 'close',
                                 ('register', 0x400c8018, 0),
                                 ('register', 0x400c8014, 0x11004000)])
        audio.pause()
        self.assertEqual(len(events), 5)

    def test_pause_aborts_before_releasing_claims(self):
        # MicroPython DMA.close() does not abort. Model that real distinction.
        from test_game_library import load
        events = []
        class Channel:
            def __init__(self, channel):
                self.channel = channel
                self.busy = True
            def pack_ctrl(self, **kw): return kw
            def config(self, **kw): events.append(('unlink',self.channel))
            def active(self, value):
                self.busy = False
                events.append(('abort',self.channel))
            def close(self):
                assert not self.busy, 'active DMA released to another owner'
                events.append(('close',self.channel))
        class Pin:
            OUT = 1
            def __init__(self,*a,**kw): pass
        module = load('retro_audio', machine=SimpleNamespace(PWM=None,Pin=Pin,mem32={}),
                      rp2=SimpleNamespace(DMA=None), uctypes=SimpleNamespace(addressof=id))
        audio = module.Audio(SimpleNamespace(audio_samples=1))
        audio.channels = [Channel(3),Channel(4)]
        audio.pause()
        self.assertEqual(events[:2],[('unlink',3),('unlink',4)])
        self.assertEqual(events[2:],[('abort',3),('close',3),('abort',4),('close',4)])
        self.assertEqual(audio.channels,[])


class StreamBlockTests(unittest.TestCase):
    def test_stream_queues_one_block_per_two_frames(self):
        # One-frame blocks left no slack: every drawn GBC frame underran.
        from test_game_library import load
        queued, configs, filled = [], [], []
        class Channel:
            def __init__(self, channel): self.channel = channel
            def pack_ctrl(self, **kw): return kw
            def active(self, value=None): return False
            def config(self, **kw): configs.append(kw.get('count'))
        class Core:
            audio_samples = 3
            audio_rate = 22039
            def audio(self, block, top, volume):
                self.check = len(block)
                filled.append(len(block))
        module = load('retro_audio', machine=SimpleNamespace(PWM=None, Pin=None, mem32={0x400c8018: 0}),
                      rp2=SimpleNamespace(DMA=None), uctypes=SimpleNamespace(addressof=id))
        module.time = SimpleNamespace(ticks_ms=lambda: 0, ticks_us=lambda: 0, ticks_add=lambda a, b: a + b,
                                      ticks_diff=lambda a, b: a - b, sleep_us=lambda n: None)
        audio = module.Audio(Core())
        audio.stream = True
        audio.fifo = SimpleNamespace(clean=lambda b: None,
                                     queue=lambda b, prev, cur: queued.append((len(b), prev, cur)) or 0)
        audio.channels = [Channel(3), Channel(4)]
        audio.controls = [{}, {}]
        size = 3 * 4
        audio.per = 2
        audio.parts = [[memoryview(b)[:size], memoryview(b)[size:]] for b in audio.buffers]
        audio.part = audio.index = 0
        audio.started = False
        audio.top = 1000
        for _ in range(4):
            audio.frame()
        self.assertEqual(filled, [size] * 4)
        self.assertEqual(configs, [6, 6])
        self.assertEqual(queued, [(2 * size, -1, 3), (2 * size, 3, 4)])


class AudioPacingTests(unittest.TestCase):
    def run_loop(self, waits):
        # Fast frames (1 ms of 16.7): without audio the loop sleeps to pace.
        state = {'us': 0, 'frames': 0}
        sleeps = []
        class Done(Exception): pass
        class Audio:
            slack_us = 15000
            def __init__(self, core, volume): self.volume = volume
            def resume(self): pass
            def pause(self): pass
            def frame(self):
                if waits:
                    state['us'] += 15000  # blocked until playback drained
                return waits
        def frame(*args):
            state['frames'] += 1
            if state['frames'] > 20: raise Done()
            state['us'] += 1000
        core = SimpleNamespace(init=lambda *a:0, palette=lambda *a:None, frame=frame)
        if waits is not None:
            core.audio = True
        def sleep_us(n):
            sleeps.append(n)
            state['us'] += n
        env = dict(gc=SimpleNamespace(collect=lambda:None), wait_for_pad=lambda:None,
                   message=lambda *a:None, short_name=lambda p:p, read_rom=lambda p:bytearray(4),
                   load_core=lambda p:(core,16688), extension=lambda p:'.gg', SHADES=(0,1,2,3),
                   zoom_for=lambda p:False, system_for=lambda p:('GG',), StateSlots=lambda *a:None,
                   MenuChord=lambda:SimpleNamespace(poll=lambda held,now:(held,False)),
                   clear_game=lambda:None,
                   EmulationClock=lambda:SimpleNamespace(resume=lambda:None, pause=lambda:None),
                   volume_for=lambda p:60, pad=SimpleNamespace(connected=True, poll=lambda now:0),
                   ui=None, fb=bytearray(4), presto=SimpleNamespace(update=lambda:None),
                   save=lambda *a:None, SAVE_EVERY_MS=10**9,
                   time=SimpleNamespace(ticks_ms=lambda:state['us']//1000, ticks_us=lambda:state['us'],
                                        ticks_add=lambda a,b:a+b, ticks_diff=lambda a,b:a-b,
                                        sleep_us=sleep_us))
        functions('device/lib/retro.py', ['run'], env)
        with patch.dict(sys.modules, {'retro_audio':SimpleNamespace(Audio=Audio)}):
            with self.assertRaises(Done): env['run']('/test.gg')
        return sleeps

    def test_audio_paces_alone_without_a_second_sleep(self):
        self.assertEqual(self.run_loop(True), [])

    def test_without_audio_the_frame_clock_still_sleeps(self):
        self.assertTrue(self.run_loop(None))

    def test_early_frames_do_not_sleep_while_audio_runs(self):
        # Between queue frames the producer may run ahead; audio holds it back.
        self.assertEqual(self.run_loop(False), [])


class SlackTests(unittest.TestCase):
    def test_little_playback_slack_drops_the_next_picture(self):
        # Two drawn GBC frames must not overrun one two-frame sound block.
        state = {'us': 0, 'n': 0}
        draws = []
        class Done(Exception): pass
        class Audio:
            def __init__(self, core, volume): self.volume = volume; self.slack_us = 0
            def resume(self): pass
            def pause(self): pass
            def frame(self):
                state['n'] += 1
                if state['n'] % 2:
                    return False
                self.slack_us = 1000 if draws[-2:] == [True, True] else 12000
                return True
        def frame(fb, keys, x, y, draw, scale):
            draws.append(draw)
            if len(draws) > 40: raise Done()
            state['us'] += 9000 if draw else 4000
        core = SimpleNamespace(init=lambda *a:0, palette=lambda *a:None, frame=frame, audio=True)
        env = dict(gc=SimpleNamespace(collect=lambda:None), wait_for_pad=lambda:None,
                   message=lambda *a:None, short_name=lambda p:p, read_rom=lambda p:bytearray(4),
                   load_core=lambda p:(core,16742), extension=lambda p:'.gbc', SHADES=(0,1,2,3),
                   zoom_for=lambda p:False, system_for=lambda p:('GBC',), StateSlots=lambda *a:None,
                   MenuChord=lambda:SimpleNamespace(poll=lambda held,now:(held,False)),
                   clear_game=lambda:None,
                   EmulationClock=lambda:SimpleNamespace(resume=lambda:None, pause=lambda:None),
                   volume_for=lambda p:60, pad=SimpleNamespace(connected=True, poll=lambda now:0),
                   ui=None, fb=bytearray(4), presto=SimpleNamespace(update=lambda:None),
                   save=lambda *a:None, SAVE_EVERY_MS=10**9,
                   time=SimpleNamespace(ticks_ms=lambda:state['us']//1000, ticks_us=lambda:state['us'],
                                        ticks_add=lambda a,b:a+b, ticks_diff=lambda a,b:a-b,
                                        sleep_us=lambda n:None))
        functions('device/lib/retro.py', ['run'], env)
        with patch.dict(sys.modules, {'retro_audio':SimpleNamespace(Audio=Audio)}):
            with self.assertRaises(Done): env['run']('/test.gbc')
        self.assertIn(False, draws)              # tight slack drops pictures
        self.assertGreater(draws.count(True), 20)  # roomy slack draws again
