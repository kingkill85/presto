"""Check the fixed-point output independently of hardware imports."""
import ast
from pathlib import Path
import unittest


def expansion():
    tree = ast.parse((Path(__file__).resolve().parents[1]/'device/lib/scumm_audio.py').read_text())
    nodes = [node for node in tree.body
             if (isinstance(node, ast.FunctionDef) and node.name == '_expand') or
             (isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'HP_A')]
    for node in nodes:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    scope = {'ptr32': lambda value: value}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<scumm output>', 'exec'), scope)
    return scope['_expand']


class AudioOutputTests(unittest.TestCase):
    def setUp(self):
        self.expand = expansion()
        self.top = 4534
        self.middle = self.top//2

    def block(self, amplitude):
        values = [self.middle+amplitude, self.middle-amplitude]*2048
        return [v<<16 for v in values]+[0]*4096

    def sine(self, amplitude, period=20):
        import math
        values = [self.middle+round(amplitude*math.sin(2*math.pi*i/period)) for i in range(4096)]
        return [v<<16 for v in values]+[0]*4096

    def deviation(self, block):
        return [(v>>16)-self.middle for v in block]

    def test_large_signal_has_headroom_without_flattening_or_rate_change(self):
        block = self.block(2200)
        self.expand(block, self.top, [1024, 0, 0], 100)
        duties = [v>>16 for v in block]
        self.assertGreater(min(duties), 0)
        self.assertLess(max(duties), self.top)
        self.assertEqual(duties[::2], duties[1::2])
        self.assertGreater(duties[0], self.middle)
        self.assertLess(duties[2], self.middle)

    def test_volume_scales_output_and_zero_really_mutes(self):
        blocks = [self.block(600) for _ in range(3)]
        for block,volume in zip(blocks,(0,30,100)):
            self.expand(block,self.top,[256,0,0],volume)
        self.assertTrue(all(v == self.middle<<16 for v in blocks[0]))
        quiet = (blocks[1][2]>>16)-self.middle
        loud = (blocks[2][2]>>16)-self.middle
        self.assertAlmostEqual(quiet/loud,0.3,places=2)

    def test_quiet_passages_gain_gradually_without_dc_offset(self):
        block = [self.middle<<16]*8192
        state = [256, 0, 0]
        gain = self.expand(block,self.top,state,100)
        self.assertGreater(gain,256)
        self.assertLessEqual(gain,256+17)
        self.assertEqual(state[0], gain)
        self.assertTrue(all(v == self.middle<<16 for v in block))

    def test_bass_and_dc_are_removed(self):
        # The piezo cannot play them; they would only eat PWM range.
        state = [256, 0, 0]
        dc = [(self.middle+800)<<16]*4096+[0]*4096
        self.expand(dc, self.top, state, 100)
        self.assertLessEqual(abs(self.deviation(dc)[-1]), 2)
        bass = self.sine(800, period=441)  # 50 Hz
        treble = self.sine(800, period=11)  # 2 kHz
        for block in (bass, treble):
            self.expand(block, self.top, [256, 0, 0], 100)
        self.assertLess(max(map(abs, self.deviation(bass)[4096:])),
                        max(map(abs, self.deviation(treble)[4096:]))/4)

    def test_peaks_are_soft_limited_below_full_scale(self):
        # Quiet body with rare loud spikes: mean normalization raises the
        # body, the limiter bends the spikes instead of clipping at full scale.
        block = self.sine(150, period=11)
        for i in range(0, 4096, 256):
            block[i] = (self.middle+2200) << 16
        self.expand(block, self.top, [1536, 0, 0], 100)
        peak = max(map(abs, self.deviation(block)))
        self.assertLessEqual(peak, self.middle*95//100)
        self.assertGreater(peak, self.middle*60//100)

    def test_steady_music_settles_near_thirty_percent_mean_level(self):
        state = [256, 0, 0]
        for _ in range(60):
            block = self.sine(300, period=11)
            self.expand(block, self.top, state, 100)
        level = sum(map(abs, self.deviation(block)))/len(block)
        self.assertGreater(level, self.middle*0.25)
        self.assertLess(level, self.middle*0.40)


class ChunkSchedulingTests(unittest.TestCase):
    def test_each_prepare_does_one_chunk_and_partial_buffers_cannot_play(self):
        tree = ast.parse((Path(__file__).resolve().parents[1]/'device/lib/scumm_audio.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_Source')
        calls = []
        scope = {'PWM_SAMPLES':8192, '_expand':lambda *args:256, 'array':lambda kind, values:list(values)}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'<chunk source>','exec'),scope)
        from types import SimpleNamespace
        buffers = (memoryview(bytearray(32768)), memoryview(bytearray(32768)))
        core = SimpleNamespace(audio=lambda *args:calls.append(args),audio_samples=1024,audio_rate=22050)
        source = scope['_Source'](core,buffers)
        for count in range(1,5):
            ready = source.prepare(buffers[0],4534,60)
            self.assertEqual(len(calls),count)
            self.assertEqual(ready,count==4)
            if not ready:
                with self.assertRaises(RuntimeError):source.audio(buffers[0],4534,60)
        source.audio(buffers[0],4534,60)
        self.assertEqual(source.part,0)
        source.prepare(buffers[1],4534,60)
        source.reset()  # menu/exception discards partial samples
        self.assertEqual(source.part,0)
        with self.assertRaises(RuntimeError):source.audio(buffers[1],4534,60)


class DisplayPriorityTests(unittest.TestCase):
    def load_priority(self):
        from collections import defaultdict
        registers = defaultdict(int)
        tree=ast.parse((Path(__file__).resolve().parents[1]/'device/lib/scumm_audio.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_DisplayPriority')
        scope={'mem32':registers}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'<display priority>','exec'),scope)
        return scope['_DisplayPriority'](),registers

    def test_only_display_chain_priority_changes_and_is_restored(self):
        priority,regs=self.load_priority()
        targets={3:0x50300018,5:0x50300010,4:0x500000fc,6:0x5000017c,2:0x5020001c}
        for channel,target in targets.items():
            base=0x50000000+channel*64
            regs[base+4]=target
            regs[base+12]=1
            regs[base+0x10]=0x200001 | (2 if channel==5 else 0)
        original=dict(regs)
        priority.enable()
        for channel in (3,4,5,6):
            self.assertTrue(regs[0x50000000+channel*64+0x10]&2)
        self.assertEqual(regs[0x50000000+2*64+0x10],original[0x50000000+2*64+0x10])
        priority.restore()
        self.assertFalse(priority.saved)
        for address,value in original.items():self.assertEqual(regs[address],value)

    def test_unknown_layout_fails_before_mutating_any_channel(self):
        priority,regs=self.load_priority()
        with self.assertRaises(RuntimeError):priority.enable()
        self.assertFalse(priority.saved)
        self.assertTrue(all(value==0 for value in regs.values()))
