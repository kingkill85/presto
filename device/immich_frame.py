# ICON photo-library
# NAME Immich
# DESC Random photos from Immich
#
# Photo frame for Immich: shows a random photo, a new one every INTERVAL
# seconds. Tap for the next photo, hold for a second to go back to the menu.
#
# Immich's own previews are JPEGs this decoder can't read (extended
# sequential) or WebP, so it loads the original JPEG instead and lets the
# decoder scale it down by 2/4/8 and crop it to the square screen. Photos are
# cached on the SD card: the frame starts instantly and keeps going offline.
#
# Needs IMMICH_URL and IMMICH_KEY in secrets.py; the API key needs
# asset.read, asset.view and asset.download.
import os
import random
import time

import jpegdec
import machine
import network
import sdcard
import urequests
from presto import Presto

from secrets import IMMICH_KEY, IMMICH_URL

INTERVAL = 60          # seconds per photo
MAX_BYTES = 3000000  # skip larger originals, they take too long over WiFi
MAX_CACHED = 300       # photos kept on the SD card
MIN_CACHED = 30        # below this, a tap downloads a new photo
CACHE = "/sd/immich"

presto = Presto(ambient_light=False, full_res=True)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()
BLACK = display.create_pen(0, 0, 0)
GREY = display.create_pen(120, 120, 120)
WHITE = display.create_pen(255, 255, 255)
jpeg = jpegdec.JPEG(display)
touch = presto.touch

for i in range(7):
    presto.set_led_rgb(i, 0, 0, 0)


def message(text):
    display.set_pen(BLACK)
    display.clear()
    display.set_pen(GREY)
    display.set_font("bitmap8")
    w = display.measure_text(text, 2)
    display.text(text, (WIDTH - w) // 2, HEIGHT // 2 - 8, WIDTH, 2)
    presto.update()


try:
    spi = machine.SPI(0, sck=machine.Pin(34, machine.Pin.OUT), mosi=machine.Pin(35, machine.Pin.OUT), miso=machine.Pin(36, machine.Pin.OUT))
    os.mount(sdcard.SDCard(spi, machine.Pin(39)), "/sd")
    try:
        os.mkdir(CACHE)
    except OSError:
        pass
    has_sd = True
except OSError:
    has_sd = False
    CACHE = "/ramfs"  # no SD card: keep only the current photo in RAM

wlan = network.WLAN(network.STA_IF)
try:
    from secrets import WIFI_PASSWORD, WIFI_SSID
    if not wlan.isconnected():
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
except Exception:
    pass

HEADERS = {"x-api-key": IMMICH_KEY}
API = IMMICH_URL.rstrip("/") + "/api"
candidates = []
current = None


def cached():
    return [f for f in os.listdir(CACHE) if f.endswith(".jpg")]


def usable(asset):
    exif = asset.get("exifInfo") or {}
    return (asset.get("originalMimeType") == "image/jpeg"
            and 0 < (exif.get("fileSizeInByte") or 0) <= MAX_BYTES
            # The decoder ignores EXIF rotation, so turned photos would show sideways.
            and str(exif.get("orientation") or "1") in ("0", "1"))


def next_asset():
    while not candidates:
        r = urequests.post(API + "/search/random", headers=HEADERS,
                           json={"size": 25, "type": "IMAGE", "withExif": True})
        found = [a["id"] for a in r.json() if usable(a)]
        r.close()
        candidates.extend(found)
    return candidates.pop()


def download():
    # Stream the original to the cache in chunks; returns the file path.
    asset = next_asset()
    path = "%s/%s.jpg" % (CACHE, asset)
    r = urequests.get("%s/assets/%s/original" % (API, asset), headers=HEADERS)
    try:
        if r.status_code != 200:
            raise OSError("HTTP %d" % r.status_code)
        buf = bytearray(16384)
        with open(path + ".part", "wb") as f:
            while True:
                n = r.raw.readinto(buf)
                if not n:
                    break
                f.write(memoryview(buf)[:n])
    finally:
        r.close()
    os.rename(path + ".part", path)

    files = cached()
    if not has_sd:
        for f in files:
            if CACHE + "/" + f != path:
                os.remove(CACHE + "/" + f)
    elif len(files) > MAX_CACHED:
        os.remove(CACHE + "/" + random.choice([f for f in files if CACHE + "/" + f != path]))
    return path


def show(path):
    jpeg.open_file(path)
    w, h = jpeg.get_width(), jpeg.get_height()
    # Largest reduction that still fills the screen; small photos stay 1:1.
    scale, div = jpegdec.JPEG_SCALE_FULL, 1
    for s, d in ((jpegdec.JPEG_SCALE_EIGHTH, 8), (jpegdec.JPEG_SCALE_QUARTER, 4), (jpegdec.JPEG_SCALE_HALF, 2)):
        if min(w, h) // d >= WIDTH:
            scale, div = s, d
            break
    display.set_pen(BLACK)
    display.clear()
    jpeg.decode((WIDTH - w // div) // 2, (HEIGHT - h // div) // 2, scale)
    presto.update()
    global current
    current = path


def busy():
    # Small dot in the corner while a photo downloads, over the current one.
    display.set_pen(BLACK)
    display.circle(WIDTH - 20, HEIGHT - 20, 9)
    display.set_pen(WHITE)
    display.circle(WIDTH - 20, HEIGHT - 20, 6)
    presto.update()


def show_cached():
    files = [f for f in cached() if CACHE + "/" + f != current]
    if not files:
        return False
    path = CACHE + "/" + random.choice(files)
    try:
        show(path)
    except Exception:
        os.remove(path)
        return False
    return True


def show_new():
    # A fresh photo from Immich, or a cached one when that fails. Some JPEGs
    # are progressive, which the decoder can't read; those are deleted and
    # the next photo is tried.
    for _ in range(5):
        if not wlan.isconnected():
            break
        busy()
        try:
            path = download()
        except Exception as e:
            print("Immich:", e)
            break
        try:
            show(path)
            return True
        except Exception:
            os.remove(path)
    return show_cached()


if not show_cached():
    message("Lade Foto ...")
    for _ in range(40):
        if wlan.isconnected():
            break
        time.sleep(0.25)
    if not show_new():
        message("Keine Fotos - WLAN/Immich?")

last = time.time()
pressed_at = None

while True:
    touch.poll()
    if touch.state:
        if pressed_at is None:
            pressed_at = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), pressed_at) > 1000:
            message("Menue ...")
            machine.reset()
    elif pressed_at is not None:
        pressed_at = None
        # Fill the cache first so tapping doesn't cycle through a handful of
        # photos; after that, tapping is instant.
        if len(cached()) < MIN_CACHED or not show_cached():
            show_new()
        last = time.time()

    if time.time() - last >= INTERVAL:
        show_new()
        last = time.time()
    time.sleep_ms(20)
