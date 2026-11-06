"""Launch only one native engine per reset; carry selection in volatile RAM."""
import json
import machine
import os


def take_request():
    try:
        with open('/ramfs/game.json') as f:
            request = json.load(f)
        os.remove('/ramfs/game.json')
        return request
    except OSError:
        return {}


def queue(app='games.py', request=None):
    if app not in ('games.py', 'gb.py', 'scumm.py', 'doom.py'):
        raise ValueError('Unknown game runtime')
    with open('/ramfs/game.json', 'w') as f:
        json.dump(request or {}, f)
    with open('/ramfs/launch.txt', 'w') as f:
        f.write(app)


def launch(app='games.py', request=None):
    queue(app, request)
    machine.reset()


def mount_sd():
    try:
        os.stat('/sd')
    except OSError:
        import sdcard
        spi = machine.SPI(0, sck=machine.Pin(34), mosi=machine.Pin(35), miso=machine.Pin(36))
        try:
            os.mount(sdcard.SDCard(spi, machine.Pin(39), baudrate=8000000), '/sd')
        except OSError:
            pass
