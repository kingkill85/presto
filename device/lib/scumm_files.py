"""Experimental read-only VFS bridge for the native SCUMM runtime.

Not an app/engine. Keep the session and arena alive throughout native calls;
always close both in finally blocks, including on native callback exceptions.
"""
import os


class ReadSession:
    def __init__(self):
        self.files = {}
        self.next_handle = 1

    def __call__(self, op, handle, value):
        if op == 0:  # open(path) -> positive handle, zero on failure
            stream = None
            try:
                size = os.stat(handle)[6]
                if size > 0x7fffffff:
                    return 0
                stream = open(handle, 'rb')
                key = self.next_handle
                self.files[key] = (stream, size)
                self.next_handle += 1
                return key
            except OSError:
                if stream is not None:
                    stream.close()
                return 0
        entry = self.files.get(handle)
        if entry is None:
            return -1
        stream, size = entry
        try:
            if op == 1:
                stream.close()
                del self.files[handle]
                return 0
            if op == 2:
                # This temporary bytearray aliases native memory. Never retain
                # it: its lifetime ends when the callback returns.
                return stream.readinto(value)
            if op == 3:
                return stream.tell()
            if op == 4:
                return size
            if op == 5:
                stream.seek(value)
                return 0
        except OSError:
            return -1
        return -1

    def close(self):
        for stream, _ in self.files.values():
            try:
                stream.close()
            except OSError:
                pass
        self.files.clear()
