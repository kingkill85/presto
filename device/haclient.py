# Non-blocking Home Assistant REST client: one request spread over many frames.
import json
import socket
import time


class HAClient:
    """Fetches /api/states/<entity> for a list of entities, one after another,
    without ever blocking: call poll() once per frame."""

    def __init__(self, host, port, token, entities, gap_ms=1500, timeout_ms=6000):
        self.addr = socket.getaddrinfo(host, port)[0][-1]
        self.host = host
        self.token = token
        self.entities = list(entities)
        self.gap_ms = gap_ms
        self.timeout_ms = timeout_ms
        self.states = {}  # entity_id -> {"state": ..., "attributes": {...}}
        self.i = 0
        self.sock = None
        self.next_at = 0
        self.errors = 0

    def _close(self, now):
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.next_at = time.ticks_add(now, self.gap_ms)

    def poll(self, now):
        if self.sock is None:
            if time.ticks_diff(now, self.next_at) < 0 or not self.entities:
                return
            self.eid = self.entities[self.i % len(self.entities)]
            self.i += 1
            self.out = ("GET /api/states/%s HTTP/1.0\r\nHost: %s\r\nAuthorization: Bearer %s\r\n\r\n"
                        % (self.eid, self.host, self.token)).encode()
            self.buf = b""
            self.started = now
            self.sock = socket.socket()
            self.sock.setblocking(False)
            try:
                self.sock.connect(self.addr)
            except OSError:
                pass  # EINPROGRESS: connecting in the background
            return
        if time.ticks_diff(now, self.started) > self.timeout_ms:
            self.errors += 1
            self._close(now)
            return
        try:
            if self.out:
                n = self.sock.send(self.out)
                if n:
                    self.out = self.out[n:]
                return
            chunk = self.sock.recv(1024)
        except OSError:
            return  # not connected yet / no data yet
        if chunk:
            self.buf += chunk
            return
        # connection closed: response complete
        head, _, body = self.buf.partition(b"\r\n\r\n")
        if head.startswith(b"HTTP/1.") and b" 200 " in head.split(b"\r\n")[0]:
            try:
                data = json.loads(body)
                self.states[self.eid] = {"state": data.get("state"), "attributes": data.get("attributes", {})}
            except ValueError:
                self.errors += 1
        else:
            self.errors += 1
        self._close(now)
