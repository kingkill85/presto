"""Optional Qw/ST Pad on the Presto's external I2C port.

Button pins follow Pimoroni's QwSTPad register map:
https://github.com/pimoroni/qwstpad-micropython
No dependency on the desk UI; Game Boy bits match gbcore.frame().
"""

import machine
import time

A, B, SELECT, START = 1, 2, 4, 8
RIGHT, LEFT, UP, DOWN = 16, 32, 64, 128
X, Y = 256, 512
DIRECTIONS = RIGHT | LEFT | UP | DOWN
ADDRESSES = (0x21, 0x23, 0x25, 0x27)
# (TCA9555 input bit, application button)
BUTTONS = ((14, A), (12, B), (11, START), (5, SELECT),
           (3, RIGHT), (2, LEFT), (1, UP), (4, DOWN), (15, X), (13, Y))


class Gamepad:
    def __init__(self, bus=None):
        self.bus = bus
        self.address = None
        self.buttons = self.pressed = self.actions = 0
        self.next_poll = time.ticks_ms()
        self.repeat_at = self.next_poll
        self.direction = 0
        self.buffer = bytearray(2)

    @property
    def connected(self):
        return self.address is not None

    def poll(self, now=None):
        """Held buttons; pressed is edges, actions adds D-pad menu repeat.

        A missing pad is retried once a second, not on every animation frame.
        Any bus failure releases all buttons, including held emulator keys.
        """
        if now is None:
            now = time.ticks_ms()
        self.pressed = self.actions = 0
        if time.ticks_diff(now, self.next_poll) < 0:
            return self.buttons
        self.next_poll = time.ticks_add(now, 8)
        try:
            if self.bus is None:
                self.bus = machine.I2C(0, sda=machine.Pin(40), scl=machine.Pin(41),
                                       freq=400000, timeout=2000)
            if self.address is None:
                for address in ADDRESSES:
                    try:
                        self.bus.readfrom_mem_into(address, 0, self.buffer)
                        # Inputs, active low; leave LED pins as inputs (LEDs off).
                        self.bus.writeto_mem(address, 6, b"\xff\xff")
                        self.bus.writeto_mem(address, 4, b"\x00\x00")
                        self.address = address
                        break
                    except OSError:
                        pass
                if self.address is None:
                    raise OSError("Qw/ST Pad absent")
            self.bus.readfrom_mem_into(self.address, 0, self.buffer)
        except OSError:
            self.address = None
            self.buttons = self.direction = 0
            self.next_poll = time.ticks_add(now, 1000)
            return 0
        raw = ~(self.buffer[0] | self.buffer[1] << 8)
        held = 0
        for bit, button in BUTTONS:
            if raw & (1 << bit):
                held |= button
        self.pressed = held & ~self.buttons
        self.buttons = held
        self.actions = self.pressed
        direction = held & DIRECTIONS
        if direction != self.direction:
            self.direction = direction
            self.repeat_at = time.ticks_add(now, 400)
        elif direction and time.ticks_diff(now, self.repeat_at) >= 0:
            self.actions |= direction
            self.repeat_at = time.ticks_add(now, 140)
        return held
