# Shared Retro console: lazy native GB/GBC/GG/NES/SMS cores, gamepad only.
# No overlays during gameplay; direct framebuffer and exact integer scaling.

import machine
import os
import time

from retro_roms import SYSTEMS, discover, extension, load_core, system_for
from gamepad import A, B, DOWN, START, UP, X, Y, Gamepad
from presto import Presto
from picographics import PicoGraphics, DISPLAY_PRESTO_FULL_RES, PEN_RGB565

presto = Presto(ambient_light=False, full_res=True, layers=1, direct_to_fb=True)
display = presto.display
touch = presto.touch
W, H = display.get_bounds()
fb = memoryview(display)
pad = Gamepad()
menu_display = None

FRAME_US = 16742  # 59.73 Hz
SAVE_EVERY_MS = 30000
SHADES = [display.create_pen(*rgb) for rgb in ((155, 188, 15), (139, 172, 15), (48, 98, 48), (15, 56, 15))]
BG = display.create_pen(40, 40, 52)
FRAME = display.create_pen(20, 20, 28)
BUTTON = display.create_pen(150, 30, 70)
LABEL = display.create_pen(200, 200, 210)
DIM = display.create_pen(110, 110, 125)
BLACK = display.create_pen(0, 0, 0)


def mount_sd():
    try:
        import sdcard
        spi = machine.SPI(0, sck=machine.Pin(34, machine.Pin.OUT), mosi=machine.Pin(35, machine.Pin.OUT),
                          miso=machine.Pin(36, machine.Pin.OUT))
        os.mount(sdcard.SDCard(spi, machine.Pin(39), baudrate=8000000), "/sd")
    except OSError:
        pass


def find_roms():
    return discover()


def menu_buffer():
    global menu_display
    if menu_display is None:
        menu_display = PicoGraphics(DISPLAY_PRESTO_FULL_RES, pen_type=PEN_RGB565, layers=1)
    return menu_display


def show_menu(surface):
    # Copy a completed menu image; never clear the live scanout while composing.
    presto.presto.update(surface)


def message(text, detail=""):
    display = menu_buffer()
    display.set_pen(BG)
    display.clear()
    display.set_pen(LABEL)
    display.text(text, 20, H // 2 - 30, W - 40, 3)
    display.set_pen(DIM)
    display.text(detail, 20, H // 2 + 15, W - 40, 2)
    show_menu(display)


def back_on_touch():
    """Allow leaving a waiting screen even when there is no gamepad."""
    touch.poll()
    if touch.state:
        machine.reset()


def wait_for_pad():
    pad.poll()
    if pad.connected:
        return
    message("Gamepad anschliessen", "Tippen: zurueck")
    while not pad.connected:
        back_on_touch()
        time.sleep_ms(20)
        pad.poll()


def short_name(path):
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return name.split(" (")[0]


def draw_roms(roms, selected, offset):
    display = menu_buffer()
    display.set_pen(BG)
    display.clear()
    display.set_pen(LABEL)
    display.text("RETRO", 20, 16, -1, 3)
    for i, path in enumerate(roms[offset:offset + 9]):
        display.set_pen(BUTTON if offset + i == selected else FRAME)
        display.rectangle(12, 64 + i * 44, W - 24, 40)
        display.set_pen(LABEL)
        label = SYSTEMS[extension(path)][0]
        display.text(label, 24, 76 + i * 44, -1, 2)
        display.text(short_name(path)[:27], 100, 76 + i * 44, -1, 2)
    show_menu(display)


def choose(roms):
    selected = 0
    shown = None
    while True:
        pad.poll()
        if not pad.connected:
            wait_for_pad()
            shown = None
            continue
        if pad.pressed & (B | X):
            machine.reset()
        if pad.actions & UP:
            selected = (selected - 1) % len(roms)
        elif pad.actions & DOWN:
            selected = (selected + 1) % len(roms)
        offset = selected // 9 * 9
        if selected != shown:
            draw_roms(roms, selected, offset)
            shown = selected
        if pad.pressed & (A | START):
            return roms[selected]
        back_on_touch()
        time.sleep_ms(20)


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
    zoomable = extension(path) in ('.nes', '.sms')
    scale = 2 if zoomable else True
    # CPU/video timing always advances at the console's original frame rate.
    # NES/SMS draw at most every other frame (~30Hz). If drawing overruns
    # the deadline, run CPU-only frames until caught up, preserving game speed.
    render_every = 2 if zoomable else 1
    frame_no = 0
    next_draw = 0
    clear_game()
    exit_since = None
    next_t = time.ticks_us()
    skip = False
    last_save = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        held = pad.poll(now)
        if not pad.connected:
            save(ram, sav)
            wait_for_pad()  # no core frames while disconnected; RAM stays alive
            clear_game()
            next_t = time.ticks_us()
            last_save = time.ticks_ms()
            skip, exit_since = False, None
            frame_no = 0
            next_draw = 0
            continue
        if (held & (X | Y)) == (X | Y):
            if exit_since is None:
                exit_since = now
            elif time.ticks_diff(now, exit_since) >= 1000:
                save(ram, sav)
                machine.reset()
        else:
            exit_since = None
        if zoomable and pad.pressed & Y and not held & X:
            scale = 3 - scale
            clear_game()
            skip = False
            next_t = time.ticks_us()
            frame_no = 0
            next_draw = 0
        draw = not skip and frame_no >= next_draw
        if draw:
            next_draw = frame_no + render_every
        err = gbcore.frame(fb, held & 0xff, 0, 0, draw, scale)
        frame_no += 1
        if err:
            print("emulator error", err)
        if draw:
            presto.update()
        next_t = time.ticks_add(next_t, frame_us)
        late = time.ticks_diff(time.ticks_us(), next_t)
        if late < 0:
            time.sleep_us(-late)
            skip = False
        else:
            skip = late > frame_us // 2 and (zoomable or not skip)
            if late > 200000:
                next_t = time.ticks_us()
        now = time.ticks_ms()
        if ram is not None and time.ticks_diff(now, last_save) > SAVE_EVERY_MS:
            if save_needed is None or save_needed():
                save(ram, sav)
            last_save = now


def main():
    wait_for_pad()
    mount_sd()
    roms = find_roms()
    if not roms:
        message("Keine ROMs", ".gb .gbc .gg .nes .sms nach /sd/roms")
        while True:
            pad.poll()
            back_on_touch()
            if pad.pressed:
                machine.reset()
            time.sleep_ms(50)
    while True:
        path = choose(roms)
        try:
            run(path)
        except (ImportError, ValueError, OSError, MemoryError) as error:
            message("Start nicht moeglich", str(error))
            # Give the player time to read it and release the launch button.
            time.sleep_ms(500)
            while True:
                pad.poll()
                back_on_touch()
                if pad.pressed & (A | B | X):
                    machine.reset()  # release all native state before another core
                time.sleep_ms(20)
