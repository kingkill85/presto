"""Run an installed game, exercise input/zoom, and exit after 27 s.

Use `mpremote run tests/check_scumm_engine_device.py + reset` (watchdog active).
Requires scummcore, scumm_backend, scumm_files and installed Monkey Island data.
Optional CAPTURE_PATH captures the final RGB565 framebuffer for visual review.
Set PROFILE=1 before running to check the installed German Monkey Island VGA.
PROFILE=2 checks German Monkey Island 2.
"""
from scumm_backend import Backend, run
import scummcore

original = Backend.__call__
events = [(2500, (1, 27, 27)), (2530, (2, 27, 27)),
          (5500, (1, 27, 27)), (5530, (2, 27, 27)),
          (19000, (3, 110, 132)), (19030, (4, 110, 132)), (19060, (5, 110, 132))]
toggles = [(15000, False), (16000, True)]


def check(self, op, a, b):
    self.now()
    if op == 103 and toggles and self.elapsed >= toggles[0][0]:
        self.zoom = toggles.pop(0)[1]
        scummcore.zoom(self.zoom)
    if op == 103 and events and self.elapsed >= events[0][0]:
        return events.pop(0)[1]
    result = original(self, op, a, b)
    if op == 103 and result and result[0] == 10:
        assert not events and not toggles
        assert self.frames > 30
        if 'CAPTURE_PATH' in globals():
            fb = memoryview(self.presto.display)
            with open(CAPTURE_PATH, 'wb') as stream:
                for offset in range(0, len(fb), 4096):
                    self.watchdog.feed()
                    stream.write(fb[offset:offset+4096])
    return result


Backend.__call__ = check
try:
    profile = globals().get('PROFILE', 2)
    path = {1: '/sd/scumm/monkey-vga-de', 2: '/sd/scumm/monkey2-de'}[profile]
    assert run(path=path, duration=27, profile=profile) == 0
    print('PASS SCUMM engine: profile', profile, 'input, zoom switches and clean quit')
finally:
    Backend.__call__ = original
