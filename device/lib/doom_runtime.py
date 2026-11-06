"""Doom Shareware on Presto: indexed display, cooperative audio and native saves."""
import gc
import os
import time
import hashlib
import binascii
from gamepad import Gamepad, A, B, X, Y, START, SELECT, LEFT, RIGHT, UP, DOWN
from game_controls import MenuChord
from game_ui import GameUI
from game_launch import mount_sd, take_request, launch
from game_storage import StateSlots, hexhash, zoom_for, store_zoom, volume_for, store_volume
from scumm_files import ReadSession
from scumm_audio import Display, Audio, BUFFER_BYTES
from retro_clock import EmulationClock

WAD_PATHS = ('/sd/doom/doom1.wad', '/sd/doom/DOOM1.WAD')
KEYS = ((UP,0xad),(DOWN,0xaf),(LEFT,0xac),(RIGHT,0xae),
        (A,0xa3),(B,0xa2),(X,0xb8),(START,13),(SELECT,27))


def wad_identity(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        header = f.read(12)
        if len(header) != 12 or header[:4] != b'IWAD':
            raise ValueError('Keine Doom-IWAD')
        h.update(header)
        while True:
            block = f.read(16384)
            if not block:
                break
            h.update(block)
    return binascii.hexlify(h.digest()).decode()


class DoomSlots(StateSlots):
    def __init__(self, path, core, identity):
        self.core, self.identity = core, identity
        self.base = '/sd/saves'
        self.root = self.base + '/doom-' + hexhash(path.encode())[:20]
        self.supported = True

    def capabilities(self):
        return bool(self.core.capabilities()), True


class Backend:
    def __init__(self, display, pad, core, audio, path):
        self.display, self.pad, self.core, self.audio = display, pad, core, audio
        self.path = path
        self.files = ReadSession()
        self.chord = MenuChord()
        self.last_time = time.ticks_ms()
        self.elapsed = 1
        self.paused = False
        self.held = 0
        self.queue = []
        self.weapon = 0
        self.menu_requested = False
        self.disconnected = False
        self.frames = 0
        self.touched = False

    def reset_time(self):
        self.last_time = time.ticks_ms()

    def input(self):
        now = time.ticks_ms()
        held, menu = self.chord.poll(self.pad.poll(now), now)
        if menu:
            self.menu_requested = True
        self.disconnected = not self.pad.connected
        touch = self.display.touch
        touch.poll()
        touching = bool(touch.state)
        if touching and not self.touched and touch.y < 60:
            self.menu_requested = True
        self.touched = touching
        if self.menu_requested or self.disconnected:
            held = 0
        changed = held ^ self.held
        for mask, key in KEYS:
            if changed & mask:
                self.queue.append(512 | (256 if held & mask else 0) | key)
        if changed & Y:
            if held & Y:
                self.weapon = self.core.weapon_key()
                self.queue.append(768 | self.weapon)
            elif self.weapon:
                self.queue.append(512 | self.weapon)
                self.weapon = 0
        self.held = held

    def __call__(self, op, a, b):
        if op < 100:
            if op == 0 and a != self.path:
                return 0
            return self.files(op, a, b)
        if op == 100:
            self.audio.pump()
            now = time.ticks_ms()
            if not self.paused:
                self.elapsed += time.ticks_diff(now, self.last_time)
            self.last_time = now
            return self.elapsed
        if op == 101:
            self.audio.pump()
            time.sleep_ms(min(a, 2))
        elif op == 102:
            if not self.queue:
                self.input()
            return self.queue.pop(0) if self.queue else 0
        elif op == 103:
            self.frames += 1
            self.display.update()
            self.audio.pump()
        elif op == 106:
            self.display.set_palette(a)
        elif op == 109:
            self.menu_requested = True
        return 0


def run(path=None, duration=0, hook=None):
    # Reserve the large contiguous arena before UI/core imports fragment PSRAM.
    gc.collect()
    arena = bytearray(5*1024*1024)
    display = Display()
    pad = Gamepad()
    ui = GameUI(display, pad)
    clock = EmulationClock()
    audio = backend = None
    result = 'exit'
    mount_sd()
    request = take_request()
    path = path or request.get('path') or WAD_PATHS[0]
    try:
        if path not in WAD_PATHS:
            raise ValueError('Nur Doom Shareware in /sd/doom wird unterstuetzt')
        ui.draw('DOOM', [], 0, 'WAD wird geprueft ...')
        identity = wad_identity(path)
        # Explicitly tested Doom 1.9 shareware. Do not advertise untested IWADs.
        if identity != '1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771':
            raise ValueError('Doom 1.9 Shareware benoetigt')
        ui.release()
        pad.poll()
        while not pad.connected:
            ui.draw('DOOM', [], 0, 'Zum Spielen: Gamepad anschliessen')
            pad.poll()
            display.touch.poll()
            if display.touch.state:
                launch('games.py', {'system': 'DOOM'})
            time.sleep_ms(100)
        ui.draw('DOOM', [], 0, 'Engine und Musik werden geladen ...')
        import doomcore
        core = doomcore
        audio = Audio(core, display, volume_for(path, 60))
        audio.pause()
        backend = Backend(display, pad, core, audio, path)
        slots = DoomSlots(path, core, identity)
        autosave = DoomSlots(path, core, identity)
        autosave.root += '-disconnect'
        zoom = zoom_for(path)
        core.zoom(zoom)
        gc.collect()
        # On-chip SRAM after the two audio queue buffers in the unused second
        # half of the P8 framebuffer (firmware v1.0.0 layout, checked by
        # Display). Doom's screen and light tables live there, not in PSRAM.
        fast = memoryview(display.presto)[2*BUFFER_BYTES:]
        core.init(arena, backend, memoryview(display.display), path, fast)
        if not duration and not request.get('restart') and autosave.info(1):
            backend.paused = True
            choice = ui.choose('DOOM', [('Automatisch fortsetzen', autosave.info(1), True),
                                       ('Neues Spiel', '', True)], 'Stand nach Gamepad-Trennung', back='Neues Spiel')
            if choice == 0:
                autosave.load(1)
            display.set_palette(display.palette_rgb)
            core.redraw()
            gc.collect()
            backend.paused = False
        backend.reset_time()
        clock.resume()
        audio.resume()
        began = time.ticks_ms()
        while not duration or time.ticks_diff(time.ticks_ms(), began) < duration:
            core.frame()
            if hook:
                hook(core, backend, slots, audio, clock)
            if backend.disconnected:
                backend.paused = True
                audio.pause()
                clock.pause()
                saved = False
                if slots.capabilities()[0]:
                    autosave.save(1)
                    saved = True
                ui.draw('GAMEPAD FEHLT', [], 0,
                        'Gespeichert. Pad verbinden.' if saved else 'Pausiert. Pad verbinden.')
                leave = False
                while not pad.connected:
                    pad.poll()
                    display.touch.poll()
                    if display.touch.state:
                        result = 'exit'
                        leave = True
                        break
                    time.sleep_ms(50)
                if leave:
                    break
                ui.release()
                backend.disconnected = False
                display.set_palette(display.palette_rgb)
                core.redraw()
                gc.collect()
                backend.paused = False
                backend.reset_time()
                clock.resume()
                audio.resume()
            if backend.menu_requested:
                backend.paused = True
                audio.pause()
                clock.pause()
                def set_zoom(value):
                    store_zoom(path, value)
                    core.zoom(value)
                def set_volume(value):
                    store_volume(path, value)
                    audio.volume = value
                action, zoom = ui.pause('Doom Shareware', zoom, slots, set_zoom,
                                        audio=audio, set_volume=set_volume)
                if action in ('exit', 'restart'):
                    result = action
                    break
                backend.menu_requested = False
                display.set_palette(display.palette_rgb)
                core.redraw()
                gc.collect()
                backend.paused = False
                backend.reset_time()
                clock.resume()
                audio.resume()
        if duration:
            print('DOOM frames', backend.frames, 'ms', time.ticks_diff(time.ticks_ms(), began),
                  'audio blocks', audio.blocks, 'underruns', audio.underruns,
                  'status', core.status(), 'free', gc.mem_free())
            return 'test'
    except (OSError, ValueError, RuntimeError, MemoryError) as error:
        if duration:
            raise
        if audio:
            audio.pause()
        clock.pause()
        ui.notice('DOOM FEHLER', str(error))
    finally:
        if audio:
            audio.pause()
        clock.pause()
        if backend:
            backend.files.close()
    if result == 'restart':
        launch('doom.py', {'system': 'DOOM', 'path': path, 'restart': True})
    launch('games.py', {'system': 'DOOM'})
