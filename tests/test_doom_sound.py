"""Synthetic DMX/MUS fixtures; no third-party game data is needed."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('DOOMGENERIC_DIR', '/tmp/presto-doomgeneric')) / 'doomgeneric'


@unittest.skipUnless(shutil.which('gcc') and (SOURCE/'i_sound.h').exists(),
                     'GCC and pinned Doomgeneric headers required (DOOMGENERIC_DIR)')
class DoomSoundTests(unittest.TestCase):
    def test_effects_music_timing_and_malformed_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp)/'sound'
            subprocess.run(['gcc', '-O2', '-DFEATURE_SOUND=1',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            '-I'+str(SOURCE), '-I'+str(ROOT/'native/doom'),
                            str(ROOT/'tests/check_doom_sound_host.c'),
                            *(str(ROOT/'native/doom'/p) for p in
                              ('sound.c', 'vendor/emu8950.c', 'vendor/emuadpcm.c')),
                            '-lm', '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)

    def test_half_rate_opl_keeps_pitch_and_envelope(self):
        results = []
        with tempfile.TemporaryDirectory() as tmp:
            for div in (1, 2):
                binary = Path(tmp)/('opl%d' % div)
                subprocess.run(['gcc', '-O2', '-DOPL_RATE_DIV=%d' % div,
                                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                                '-I'+str(ROOT/'native/doom'),
                                str(ROOT/'tests/check_doom_opl_rate_host.c'),
                                *(str(ROOT/'native/doom'/p) for p in
                                  ('vendor/emu8950.c', 'vendor/emuadpcm.c')),
                                '-lm', '-o', str(binary)], check=True, capture_output=True)
                out = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                results.append([float(v) for v in out.stdout.split()])
        full, half = results
        self.assertEqual(full[-1], half[-1])  # identical pitch
        self.assertGreater(full[0], 100)
        for a, b in zip(full[:-1], half[:-1]):  # RMS per 100 ms window
            self.assertLessEqual(abs(a-b), max(0.02*a, 1.0))


if __name__ == '__main__':
    unittest.main()
