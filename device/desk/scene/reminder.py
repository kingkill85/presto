# Before an appointment from the daily note, the pirate walks through the
# background, turns to you and tells you, 10 and again 2 minutes before it
# starts (each time with another line), then walks back the way he came.
# Smaller than on his visits (further away), behind Messy and Clawd, who
# carry on.

import random
import time

from desk import sound
from desk.data import herdr
from desk.gfx import WIDTH, display, draw_bubble
from desk.scene import seasons
from desk.scene.sprites import GB_W, GROUND, draw_guybrush, walk_frame

MARKS = (10, 2)  # minutes before
SCALE = 3  # pirate pixel, 4 on his visits
SPEED = 3.0  # px per 66 ms
FEET_Y = GROUND + 2  # on the grass
TALK = (1, 2, 1, 0, 2, 1, 0, 0)  # mouth while talking

SOON = ("DENK DRAN!", "TERMIN GLEICH!", "AHOI! TERMIN!", "NICHT VERGESSEN!", "GLEICH GEHTS LOS!",
        "TERMIN, MATROSE!")  # 10 minutes before
NOW = ("JETZT ABER LOS!", "LOS, LOS, LOS!", "ES GEHT LOS!", "ANKER LICHTEN!", "AB ZUM TERMIN!")  # 2 minutes

STOP_X = WIDTH // 2 - 24  # where he stops to talk
OFF_X = -GB_W * SCALE - 4  # off the screen on the left
TALK_MS = 3200

_walk = None  # {"x", "t0", "text", "dir": 1 in / -1 back, "talk": when he stopped or None}
_done = set()  # (date, time, mark) already shown


def active():
    return _walk is not None


def update(now, k, busy):
    """Start a walk when a mark is reached (not while `busy`), move him on:
    in to the middle, turn and talk, then back out to the left."""
    global _walk
    if _walk:
        w = _walk
        if w["talk"] is not None:
            if time.ticks_diff(now, w["talk"]) > TALK_MS:
                w["talk"], w["dir"], w["t0"] = None, -1, now
        elif w["dir"] > 0 and w["x"] >= STOP_X:
            w["talk"] = now
        else:
            w["x"] += SPEED * k * w["dir"]
            if w["x"] < OFF_X:
                _walk = None
        return
    t = seasons.today(now)
    e = herdr.next_event(t)
    if not e or not t or busy:
        return
    left = herdr.minutes_until(e, t)
    marks = [m for m in MARKS if 0 <= left <= m and (herdr.day["date"], e["t"], m) not in _done]
    if not marks:
        return
    for m in marks:  # just one walk when several marks are due at once
        _done.add((herdr.day["date"], e["t"], m))
    _walk = {"x": OFF_X + 1, "t0": now, "talk": None, "dir": 1,
             "text": random.choice(NOW if left <= MARKS[-1] else SOON)}
    sound.play("remind")


def draw(now):
    if not _walk:
        return
    x = _walk["x"]
    top = FEET_Y - 32 * SCALE
    if _walk["talk"] is None:
        legs, arms, bob, hem, hair = walk_frame(time.ticks_diff(now, _walk["t0"]) * 3 // 2)  # quick steps
        draw_guybrush(x, flip=_walk["dir"] < 0, legs=legs, arms=arms, bob=bob, hem=hem, hair=hair, scale=SCALE, y=top)
        return
    ms = time.ticks_diff(now, _walk["talk"])
    draw_guybrush(x, mouth=TALK[(ms // 140) % len(TALK)], scale=SCALE, y=top, front=True)  # facing you
    w = display.measure_text(_walk["text"], 2) + 8
    draw_bubble(_walk["text"], max(2, min(int(x) + 30, WIDTH - w - 2)), top - 28)
