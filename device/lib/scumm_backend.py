"""Experimental Presto backend for native SCUMM-v4/v5 game profiles."""
import gc
import hashlib
import binascii
import machine
import os
import time
from scumm_files import ReadSession
from gamepad import Gamepad, A, B, X, Y, START, SELECT, LEFT, RIGHT, UP, DOWN


class FileSession(ReadSession):
    def __init__(self, save_root='/sd/scumm/saves'):
        super().__init__()
        self.dirs = {}
        self.save_root = save_root

    def path(self, path):
        if path == '/quest' or path.startswith('/quest/'):
            path = '/sd/scumm' + path[6:]
        parts = []
        for part in path.replace('\\', '/').split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part and part != '.':
                parts.append(part)
        return '/' + '/'.join(parts)

    def __call__(self, op, handle, value):
        if op in (0, 6, 7, 10, 13, 14):
            handle = self.path(handle)
        if op <= 5:
            return super().__call__(op, handle, value)
        try:
            if op == 6:
                return 2 if os.stat(handle)[0] & 0x4000 else 1
            if op == 7:
                key = self.next_handle
                iterator = os.ilistdir(handle)
                self.dirs[key] = iterator
                self.next_handle += 1
                return key
            if op == 8:
                entry = next(self.dirs[handle], None)
                if entry is None:
                    return None
                return (entry[0], entry[3] if len(entry) > 3 else 0,
                        bool(entry[1] & 0x4000))
            if op == 9:
                del self.dirs[handle]
                return 0
            if op in (10, 13, 14):
                if not (handle == self.save_root or handle.startswith(self.save_root + '/')):
                    return 0 if op == 10 else 1
                if op == 10:
                    stream = open(handle, 'wb')
                    key = self.next_handle
                    self.files[key] = (stream, 0)
                    self.next_handle += 1
                    return key
                if op == 13:
                    try:
                        os.mkdir(handle)
                    except OSError:
                        if not os.stat(handle)[0] & 0x4000:
                            return 1
                    return 0
                os.remove(handle)
                return 0
            if op == 11:
                stream, size = self.files[handle]
                written = stream.write(value)
                self.files[handle] = (stream, max(size, stream.tell()))
                return written
            if op == 12:
                self.files[handle][0].flush()
                return 0
        except (OSError, KeyError):
            if op in (6, 7, 10):
                return 0
            if op == 8:
                return None
            return -1
        return -1

    def close(self):
        self.dirs.clear()
        super().close()


class Backend:
    def __init__(self, presto, duration=0, watchdog=None, zoom=True, zoom_fn=None):
        self.presto = presto
        self.files = FileSession()
        self.pad = Gamepad()
        self.watchdog = watchdog
        self.last_tick = time.ticks_ms()
        self.elapsed = 0
        self.until = duration * 1000
        self.next_input = self.last_tick
        self.events = []
        self.x, self.y = 160, 100
        self.buttons = 0
        self.touching = False
        self.touch_down = False
        self.frames = 0
        self.quit_sent = False
        self.zoom = zoom
        self.zoom_fn = zoom_fn

    def now(self):
        tick = time.ticks_ms()
        self.elapsed += time.ticks_diff(tick, self.last_tick)
        self.last_tick = tick
        if self.watchdog:
            self.watchdog.feed()
        return self.elapsed

    def event(self):
        if self.events:
            return self.events.pop(0)
        if self.until and self.elapsed >= self.until and not self.quit_sent:
            self.quit_sent = True
            return (10, 0, 0)
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next_input) < 0:
            return None
        self.next_input = time.ticks_add(now, 16)
        held = self.pad.poll(now)
        if held & (X | Y) == X | Y:
            if not self.quit_sent:
                self.quit_sent = True
                return (10, 0, 0)
            return None
        if held & SELECT and not self.buttons & SELECT and self.zoom_fn:
            self.zoom = not self.zoom
            self.zoom_fn(self.zoom)
        old_x, old_y = self.x, self.y
        self.x = max(0, min(319, self.x + 3 * (bool(held & RIGHT) - bool(held & LEFT))))
        self.y = max(0, min(199, self.y + 3 * (bool(held & DOWN) - bool(held & UP))))
        touch = self.presto.touch
        touch.poll()
        first_touch = touch.state and not self.touch_down
        self.touch_down = bool(touch.state)
        # Controls live in the unused upper border, never over game content.
        if first_touch and touch.y < 64:
            if touch.x < 64 and not self.quit_sent:
                self.quit_sent = True
                return (10, 0, 0)
            if touch.x >= 416 and self.zoom_fn:
                self.zoom = not self.zoom
                self.zoom_fn(self.zoom)
        left, top = (0, 90) if self.zoom else (80, 140)
        width, height = (480, 300) if self.zoom else (320, 200)
        touching = touch.state and left <= touch.x < left+width and top <= touch.y < top+height
        if touching:
            self.x, self.y = touch.x - left, touch.y - top
            if self.zoom:
                self.x, self.y = self.x*2//3, self.y*2//3
        if (old_x, old_y) != (self.x, self.y):
            self.events.append((3, self.x, self.y))
        left = bool(held & A) or touching
        old_left = bool(self.buttons & A) or self.touching
        if left != old_left:
            self.events.append((4 if left else 5, self.x, self.y))
        if bool(held & B) != bool(self.buttons & B):
            self.events.append((6 if held & B else 7, self.x, self.y))
        for mask, key in ((X, 27), (Y, 32), (START, 13)):
            if bool(held & mask) != bool(self.buttons & mask):
                self.events.append((1 if held & mask else 2, key, key if key < 128 else 0))
        self.buttons, self.touching = held, touching
        return self.events.pop(0) if self.events else None

    def __call__(self, op, a, b):
        self.now()
        if op < 100:
            return self.files(op, a, b)
        if op == 100:
            return self.elapsed & 0xffffffff
        if op == 101:
            deadline = time.ticks_add(time.ticks_ms(), a)
            while True:
                remaining = time.ticks_diff(deadline, time.ticks_ms())
                if remaining <= 0:
                    break
                time.sleep_ms(min(10, remaining))
                self.now()
            return 0
        if op == 102:
            self.presto.update()
            self.frames += 1
            return 0
        if op == 103:
            return self.event()
        raise ValueError('Unsupported SCUMM callback')


GAMES = (
    (2, 'Monkey Island 2', '/sd/scumm/monkey2-de', ('monkey2.000', 'monkey2.001')),
    (1, 'Monkey Island', '/sd/scumm/monkey-vga-de',
     ('000.lfl', 'disk01.lec', 'disk02.lec', 'disk03.lec', 'disk04.lec')),
)


def installed_games():
    found = []
    for game in GAMES:
        try:
            for name in game[3]:
                os.stat(game[2] + '/' + name)
            found.append(game)
        except OSError:
            pass
    return found


def choose_game(path=None, profile=None):
    if path is None:
        games = installed_games()
        if not games:
            raise OSError('No supported SCUMM games installed')
        return games[0][2], games[0][0]
    if profile is None:
        profile = next((g[0] for g in GAMES if path.rstrip('/') == g[2]), None)
    if profile not in (1, 2):
        raise ValueError('Unknown SCUMM game profile')
    return path, profile


def choose_on_screen(presto, games):
    if len(games) == 1:
        return games[0][2], games[0][0]
    if not games:
        raise OSError('No supported SCUMM games installed')
    from picographics import PicoGraphics, DISPLAY_PRESTO_FULL_RES, PEN_RGB565
    canvas = PicoGraphics(DISPLAY_PRESTO_FULL_RES, pen_type=PEN_RGB565, layers=1)
    canvas.set_font('bitmap8')
    bg = canvas.create_pen(29, 43, 83)
    fg = canvas.create_pen(255, 241, 232)
    active = canvas.create_pen(255, 163, 0)
    inactive = canvas.create_pen(95, 87, 79)
    pad = Gamepad()
    selected, drawn = 0, -1
    touch_down = True
    ready = False
    while True:
        if selected != drawn:
            canvas.set_pen(bg)
            canvas.clear()
            canvas.set_pen(fg)
            canvas.text('SCUMM', 24, 28, scale=4)
            for row, game in enumerate(games):
                y = 105 + row * 80
                canvas.set_pen(active if row == selected else inactive)
                canvas.rectangle(20, y, 440, 62)
                canvas.set_pen(bg if row == selected else fg)
                canvas.text(game[1], 36, y + 19, scale=2)
            canvas.set_pen(fg)
            canvas.text('A / antippen: Start', 24, 365, scale=2)
            canvas.text('B / hier tippen: Zurueck', 24, 420, scale=2)
            presto.presto.update(canvas)
            drawn = selected
        held = pad.poll()
        presto.touch.poll()
        touching = bool(presto.touch.state)
        if not held and not touching:
            ready = True
        if ready:
            if pad.actions & UP:
                selected = (selected - 1) % len(games)
            elif pad.actions & DOWN:
                selected = (selected + 1) % len(games)
            if pad.pressed & (B | X):
                return None
            if pad.pressed & (A | START):
                return games[selected][2], games[selected][0]
            if touching and not touch_down:
                x, y = presto.touch.x, presto.touch.y
                if y >= 405:
                    return None
                row = (y - 105) // 80
                if 20 <= x < 460 and 0 <= row < len(games) and (y - 105) % 80 < 62:
                    return games[row][2], games[row][0]
        touch_down = touching
        time.sleep_ms(16)


def run(path=None, duration=0, profile=None):
    from presto import Presto
    import sdcard
    presto = Presto(full_res=True, direct_to_fb=True, layers=1, ambient_light=False)
    try:
        os.stat('/sd')
    except OSError:
        spi = machine.SPI(0, sck=machine.Pin(34), mosi=machine.Pin(35), miso=machine.Pin(36))
        os.mount(sdcard.SDCard(spi, machine.Pin(39), baudrate=8000000), '/sd')
    for directory in ('/sd/scumm', '/sd/scumm/saves'):
        try:
            os.mkdir(directory)
        except OSError:
            os.stat(directory)
    if path is None:
        selected = choose_on_screen(presto, installed_games())
        if selected is None:
            return 0
        path, profile = selected
    path, profile = choose_game(path, profile)
    # This firmware provides SHA256, but no MD5. The native profile also holds
    # the upstream MD5 identifier of the same verified edition.
    index, expected = {
        1: ('000.lfl', b'c2d8c664028d326385de016b9d781fc0a33917a1de3032b5f2fce1191baa8522'),
        2: ('monkey2.000', b'b043d9dcc8510e3565bb0152f7e35e686514837e97275aa08d3ca1fcd0924ccd'),
    }[profile]
    digest = hashlib.sha256()
    with open(path + '/' + index, 'rb') as stream:
        while True:
            block = stream.read(4096)
            if not block:
                break
            digest.update(block)
    if binascii.hexlify(digest.digest()) != expected:
        raise ValueError('Unsupported SCUMM game edition')
    import scummcore
    gc.collect()
    print('SCUMM heap before arena:', gc.mem_free())
    arena = bytearray(4 * 1024 * 1024)
    backend = Backend(presto, duration, machine.WDT(timeout=8000), zoom_fn=scummcore.zoom)
    try:
        result = scummcore.run(arena, backend, memoryview(presto.display), path, profile)
        print('SCUMM result:', result, 'frames:', backend.frames, 'ms:', backend.elapsed)
        return result
    finally:
        backend.files.close()
        scummcore.close()
