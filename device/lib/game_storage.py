"""Five checked state slots per game; battery saves remain separate."""
import os
import json
import hashlib
import binascii


def hexhash(data):
    return binascii.hexlify(hashlib.sha256(data).digest()).decode()


def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def replace(temp, path):
    # FAT cannot always rename over an existing file. Retain a recoverable copy.
    backup = path + '.bak'
    if exists(path):
        if exists(backup):
            os.remove(backup)
        os.rename(path, backup)
    try:
        os.rename(temp, path)
    except OSError:
        if exists(backup) and not exists(path):
            os.rename(backup, path)
        raise
    if exists(backup):
        os.remove(backup)


def recover(path):
    if not exists(path) and exists(path + '.bak'):
        os.rename(path + '.bak', path)
    return path


def stamp():
    from tz import localtime
    t = localtime()
    return '%02d.%02d.%04d %02d:%02d' % (t[2], t[1], t[0], t[3], t[4]) if t[0] >= 2024 else 'Gespeichert'


def read_settings():
    try:
        with open(recover('/sd/games.json')) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def zoom_for(path):
    return bool(read_settings().get(path, True))


def store_zoom(path, enabled):
    settings = read_settings()
    settings[path] = bool(enabled)
    with open('/sd/games.json.tmp', 'w') as f:
        json.dump(settings, f)
    replace('/sd/games.json.tmp', '/sd/games.json')


def volume_for(path, default=60):
    value = read_settings().get('audio:' + path, default)
    return value if isinstance(value, int) and value in (0, 30, 60, 100) else default


def store_volume(path, value):
    if value not in (0, 30, 60, 100):
        raise ValueError('Ungueltige Lautstaerke')
    settings = read_settings()
    settings['audio:' + path] = value
    with open('/sd/games.json.tmp', 'w') as f:
        json.dump(settings, f)
    replace('/sd/games.json.tmp', '/sd/games.json')


class StateSlots:
    def __init__(self, path, core, rom, root='/sd/saves'):
        self.core = core
        self.identity = hexhash(rom)
        self.base = root
        self.root = root + '/' + hexhash(path.encode())[:20]
        self.supported = all(hasattr(core, k) for k in ('state_size', 'save_state', 'load_state', 'state_id'))

    def capabilities(self):
        return self.supported, self.supported

    def path(self, slot):
        if not 1 <= slot <= 5:
            raise ValueError('Ungueltiger Speicherplatz')
        return self.root + '/slot%d.state' % slot

    def info(self, slot):
        path = recover(self.path(slot))
        if not exists(path):
            return None
        try:
            with open(path, 'rb') as f:
                meta = json.loads(f.readline(1024))
            return meta.get('date', 'Gespeichert')
        except (OSError, ValueError):
            return 'Beschaedigt'

    def save(self, slot):
        if not self.supported:
            raise ValueError('Core ohne Speicherzustaende')
        for folder in (self.base, self.root):
            if not exists(folder):
                os.mkdir(folder)
        data = bytearray(self.core.state_size())
        self.core.save_state(data)
        meta = dict(format=1, core=self.core.state_id, rom=self.identity,
                    size=len(data), checksum=hexhash(data), date=stamp())
        path = self.path(slot)
        with open(path + '.tmp', 'wb') as f:
            f.write(json.dumps(meta).encode() + b'\n')
            f.write(data)
            f.flush()
        replace(path + '.tmp', path)

    def load(self, slot):
        if not self.supported:
            raise ValueError('Core ohne Speicherzustaende')
        with open(recover(self.path(slot)), 'rb') as f:
            line = f.readline(1024)
            meta = json.loads(line)
            size = self.core.state_size()
            if (meta.get('format') != 1 or meta.get('core') != self.core.state_id
                    or meta.get('rom') != self.identity or meta.get('size') != size):
                raise ValueError('Speicherstand passt nicht zum Spiel/Core')
            data = bytearray(size)
            if f.readinto(data) != size or f.read(1):
                raise ValueError('Speicherstand unvollstaendig')
        if hexhash(data) != meta.get('checksum'):
            raise ValueError('Speicherstand beschaedigt')
        self.core.load_state(data)
