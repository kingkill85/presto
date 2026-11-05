# Shared Retro console: lazy native GB/GBC/GG/NES/SMS cores, gamepad only.
# No overlays during gameplay; direct framebuffer and exact integer scaling.

import machine
import gc
import os
import time

from retro_clock import EmulationClock
from retro_roms import extension, load_core, system_for
from gamepad import Gamepad
from game_controls import MenuChord
from game_ui import GameUI
from game_storage import StateSlots, zoom_for, store_zoom, volume_for, store_volume
from game_launch import launch, take_request
from presto import Presto

presto = Presto(ambient_light=False, full_res=True, layers=1, direct_to_fb=True)
display = presto.display
touch = presto.touch
W, H = display.get_bounds()
fb = memoryview(display)
pad = Gamepad()
ui = GameUI(presto, pad)

SAVE_EVERY_MS = 30000
SHADES = [display.create_pen(*rgb) for rgb in ((155, 188, 15), (139, 172, 15), (48, 98, 48), (15, 56, 15))]
BLACK = display.create_pen(0, 0, 0)


def mount_sd():
    try:
        import sdcard
        spi = machine.SPI(0, sck=machine.Pin(34, machine.Pin.OUT), mosi=machine.Pin(35, machine.Pin.OUT),
                          miso=machine.Pin(36, machine.Pin.OUT))
        os.mount(sdcard.SDCard(spi, machine.Pin(39), baudrate=8000000), "/sd")
    except OSError:
        pass


def message(text, detail=""):
    ui.draw(text.upper(), [], 0, detail)


def back_on_touch():
    touch.poll()
    if touch.state:
        launch()


def wait_for_pad():
    pad.poll()
    if pad.connected:
        return
    message("Gamepad anschliessen", "Tippen: zur Spiele-Auswahl")
    while not pad.connected:
        back_on_touch()
        time.sleep_ms(20)
        pad.poll()


def short_name(path):
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0].split(" (")[0]


def save(ram, path):
    if ram is None:
        return
    try:
        with open(path, "wb") as f:
            f.write(ram)
    except OSError:
        pass


def clear_game():
    display.set_pen(BLACK)
    display.clear()
    presto.update()


def read_rom(path):
    # MicroPython read() without a length grows its buffer in small increments.
    # Large color ROMs can spend a minute reallocating; allocate once instead.
    rom = bytearray(os.stat(path)[6])
    with open(path, "rb") as f:
        if f.readinto(rom) != len(rom):
            raise ValueError("ROM unvollstaendig")
    return rom


def run(path):
    wait_for_pad()  # do not load or advance a game without its controller
    message("Laden...", short_name(path))
    rom = read_rom(path)
    gbcore, frame_us = load_core(path)
    if extension(path) in ('.gg', '.sms'):
        size = gbcore.init(rom, extension(path) == '.gg')
    else:
        size = gbcore.init(rom)
    ram, sav = None, path.rsplit(".", 1)[0] + ".sav"
    if size:
        ram = bytearray(size)
        try:
            with open(sav, "rb") as f:
                f.readinto(ram)
        except OSError:
            pass
        gbcore.set_ram(ram)
        get_ram = getattr(gbcore, 'get_ram', None)
        if get_ram:
            ram = get_ram()  # live view of native cartridge RAM, not a stale copy
    gbcore.palette(*SHADES)
    save_needed = getattr(gbcore, 'save_needed', None)
    # Cores without a dirty flag (GB/GBC/NES): autosave only changed RAM. An
    # unconditional write stops sound and turbo for ~100 ms every 30 s.
    saved = bytes(ram) if ram is not None and save_needed is None else None
    zoomable = extension(path) in ('.nes', '.sms')
    zoom = zoom_for(path)
    system = system_for(path)[0]
    handheld = system in ('GB', 'GBC')
    scale = (1 if zoom else 2) if handheld else (2 if zoom else 1)
    slots = StateSlots(path, gbcore, rom)
    chord = MenuChord()
    # CPU/video timing always advances at the console's original frame rate.
    # NES draws at most every other frame (~30Hz). GB/GBC/SMS/GG try every
    # frame since their output got faster; a late frame skips its picture
    # (never two in a row for handhelds and GG). If drawing overruns
    # the deadline, run CPU-only frames until caught up, preserving game speed.
    render_every = 2 if system == 'NES' else 1
    frame_no = 0
    next_draw = 0
    clear_game()
    clock = EmulationClock()
    audio = None
    if hasattr(gbcore, 'audio'):
        from retro_audio import Audio
        audio = Audio(gbcore, volume_for(path))

    def set_volume(value):
        store_volume(path, value)
        audio.volume = value

    def pause():
        try:
            if audio:
                audio.pause()
        finally:
            clock.pause()

    def resume():
        if audio:
            gc.collect()  # Reclaim menu/state buffers before starting the audio queue.
        clock.resume()
        if audio:
            audio.resume()
    try:
        resume()
        next_t = time.ticks_us()
        skip = False
        last_save = time.ticks_ms()
        while True:
            now = time.ticks_ms()
            held = pad.poll(now)
            if not pad.connected:
                pause()
                save(ram, sav)
                wait_for_pad()  # no core frames while disconnected; RAM stays alive
                resume()
                clear_game()
                next_t = time.ticks_us()
                last_save = time.ticks_ms()
                skip = False
                frame_no = 0
                next_draw = 0
                continue
            held, menu = chord.poll(held, now)
            if menu:
                pause()
                picture = bytearray(fb)
                try:
                    action, zoom = ui.pause(short_name(path), zoom, slots,
                                             lambda value: store_zoom(path, value),
                                             audio, set_volume if audio else None)
                finally:
                    fb[:] = picture
                    del picture
                    presto.update()
                scale = (1 if zoom else 2) if handheld else (2 if zoom else 1)
                if action in ('restart', 'exit'):
                    save(ram, sav)
                    request = dict(path=path, system=system_for(path)[0])
                    launch('gb.py' if action == 'restart' else 'games.py', request)
                    return
                clear_game()
                resume()
                next_t = time.ticks_us()
                skip = False
                frame_no = next_draw = 0
                last_save = time.ticks_ms()
                continue
            draw = not skip and frame_no >= next_draw
            if draw:
                next_draw = frame_no + render_every
            err = gbcore.frame(fb, held & 0xff, 0, 0, draw, scale)
            waited = audio.frame() if audio else False
            frame_no += 1
            if err:
                print("emulator error", err)
            if draw:
                presto.update()
            next_t = time.ticks_add(next_t, frame_us)
            now_us = time.ticks_us()
            late = time.ticks_diff(now_us, next_t)
            if audio and (waited or late < 0):
                # Sound output paces emulation. Sleeping on this second clock
                # as well ate the audio buffer (GG: 17 underruns, without: 0).
                # Having waited for playback means exactly on time: rebase, so
                # rate differences between the clocks never add up to skips.
                # Little time left in that wait: drop the next picture before
                # the sound runs dry (Zelda DX draws ~18 ms frames).
                if waited:
                    next_t = now_us
                    skip = audio.slack_us < frame_us // 3
                else:
                    skip = False
            elif late < 0:
                time.sleep_us(-late)
                skip = False
            else:
                skip = late > frame_us // 2 and (zoomable or not skip)
                if late > 200000:
                    next_t = time.ticks_us()
            now = time.ticks_ms()
            if ram is not None and time.ticks_diff(now, last_save) > SAVE_EVERY_MS:
                if save_needed() if save_needed else ram != saved:
                    pause()
                    save(ram, sav)
                    resume()
                    if saved is not None:
                        saved = bytes(ram)
                last_save = now
    finally:
        pause()


def main():
    mount_sd()
    request = take_request()
    path = request.get('path')
    if not path:
        launch()
        return
    try:
        run(path)
    except (ImportError, ValueError, OSError, MemoryError, RuntimeError) as error:
        ui.notice('START NICHT MOEGLICH', str(error))
        launch('games.py', request)
