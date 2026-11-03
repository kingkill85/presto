# SCUMM: choose between supported games installed on the SD card.
# One native session per reset; the next boot returns to the desk.
import machine
import time
from scumm_backend import run

try:
    run()
except Exception as error:
    print('SCUMM start failed:', error)
    time.sleep_ms(2000)
finally:
    machine.reset()
