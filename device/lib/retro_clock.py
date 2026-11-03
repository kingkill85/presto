"""Temporary emulator clock; menus, save I/O and disconnects use the boot clock."""
import machine

TURBO_HZ = 300000000


class EmulationClock:
    def __init__(self):
        self.normal = machine.freq()
        self.target = max(self.normal, TURBO_HZ)
        self.active = False

    def resume(self):
        if self.active or self.target == self.normal:
            return
        try:
            machine.freq(self.target)
            self.active = True
        except (ValueError, OSError):
            # Other firmware may reject this frequency; keep the console usable.
            machine.freq(self.normal)
            self.target = self.normal

    def pause(self):
        if self.active:
            machine.freq(self.normal)
            self.active = False
