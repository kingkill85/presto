"""ROM discovery and core selection; importing this never loads a native core."""
import os

# label, native module, frame period in microseconds
SYSTEMS = {
    '.gb': ('GB', 'gbcore', 16742),
    '.gbc': ('GBC', 'gbccore', 16742),
    '.gg': ('GG', 'smscore', 16688),
    '.nes': ('NES', 'nescore', 16639),
    '.sms': ('SMS', 'smscore', 16688),
}
ROOTS = ('/roms', '/sd/roms')


def extension(path):
    return '.' + path.rsplit('.', 1)[-1].lower()


def system_for(path):
    ext = extension(path)
    if ext not in SYSTEMS:
        raise ValueError('Unbekanntes ROM-Format')
    # Some CGB cartridges use .gb. Detect their hardware flag, too.
    if ext == '.gb':
        with open(path, 'rb') as f:
            f.seek(0x143)
            flag = f.read(1)
        if flag and flag[0] & 0x80:
            return SYSTEMS['.gbc']
    return SYSTEMS[ext]


def discover(roots=ROOTS):
    found = []
    todo = [(root, 0) for root in roots]
    while todo:
        folder, depth = todo.pop()
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if name.startswith('.'):
                continue
            path = folder + '/' + name
            try:
                directory = os.stat(path)[0] & 0x4000
            except OSError:
                continue
            if directory:
                if depth < 8:
                    todo.append((path, depth + 1))
            elif extension(name) in SYSTEMS:
                found.append(path)
    return sorted(found, key=lambda p: (p.rsplit('/', 1)[-1].lower(), p))


def load_core(path):
    _, module, period = system_for(path)
    return __import__(module), period
