# Internal runtime; games.py owns the visible library.
import machine
import time
from game_launch import take_request, queue
from scumm_backend import run

request = take_request()
try:
    if request.get('path'):
        run(path=request['path'], profile=request.get('profile'))
    else:
        queue()
except Exception as error:
    print('SCUMM start failed:', error)
    time.sleep_ms(2000)
    queue('games.py', dict(system='SCUMM'))
finally:
    machine.reset()
