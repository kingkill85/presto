"""UDP socket for the Presto messages that also works in WSL2.

WSL2 normally sits behind a NAT network of its own: a broadcast from there
never reaches the LAN, and mirrored networking doesn't work everywhere. So in
WSL broadcasts are handed to a small Python process on the Windows side
(`python.exe`, reading hex lines from stdin), which sends them out on each of
Windows' network interfaces, wherever the laptop is. Unicast to a fixed target
gets through the NAT and is sent directly.
"""

import glob
import os
import shutil
import socket
import subprocess

BROADCAST = "255.255.255.255"

# runs on Windows: one line "port hexdata" per packet, broadcast on every
# interface (the addresses are looked up per packet, the network may change)
RELAY = r"""
import socket, sys
for line in iter(sys.stdin.buffer.readline, b""):
    try:
        port, data = line.split()
        data = bytes.fromhex(data.decode())
        ips = {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except Exception:
        continue
    for ip in ips:
        if ip.startswith(("127.", "169.254.")):
            continue
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((ip, 0))
            s.sendto(data, ("255.255.255.255", int(port)))
            s.close()
        except OSError:
            pass
"""


def windows_python():
    """Windows' python.exe when running in WSL, else None."""
    if not os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return None
    found = os.environ.get("PRESTO_WINDOWS_PYTHON") or shutil.which("python.exe") or shutil.which("py.exe")
    if found:
        return found
    # a service (systemd) doesn't have the Windows folders on its PATH
    for pattern in ("/mnt/c/Users/*/AppData/Local/Programs/Python/Python3*/python.exe",
                    "/mnt/c/Users/*/AppData/Local/Programs/Python/Launcher/py.exe",
                    "/mnt/c/Windows/py.exe"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


class Sender:
    """Like a UDP socket with SO_BROADCAST: just `sendto` and `close`."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.python = windows_python()
        self.relay = None

    def sendto(self, data, addr):
        host, port = addr
        if host != BROADCAST or not self.python:
            return self.sock.sendto(data, addr)
        if self.relay is None or self.relay.poll() is not None:  # (re)start it
            self.relay = subprocess.Popen([self.python, "-c", RELAY], stdin=subprocess.PIPE,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.relay.stdin.write(b"%d %s\n" % (port, data.hex().encode()))
            self.relay.stdin.flush()
        except OSError:  # relay died, the next packet starts a new one
            self.relay = None
        return len(data)

    def close(self):
        """Waits until the relay has sent everything (short-lived callers)."""
        if self.relay:
            try:
                self.relay.stdin.close()
                self.relay.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.relay.kill()
        self.sock.close()
