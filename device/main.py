# Boot into the start screen (desk/), or into the app picked on its apps page:
# desk/apps.py writes the file name to /ramfs/launch.txt and resets. The file
# is removed right away, so the next reset is back on the start screen.
import os

import psram

psram.mkramfs()
try:
    with open("/ramfs/launch.txt") as f:
        app = f.readline().strip()
    os.remove("/ramfs/launch.txt")
except OSError:
    app = ""

if app.endswith(".py"):
    __import__(app[:-3])
else:
    import desk.main  # noqa: F401
