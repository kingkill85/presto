# The 7 RGB LEDs on the back glow on the wall: they follow the mood of the
# scene, fading smoothly, and single LEDs can show the status of one agent.

import math

from desk.data import herdr
from desk.gfx import presto

COUNT = 7
_base = [0.0, 0.0, 0.0]  # the shared mood colour, fading
_shown = [None] * COUNT  # what each LED shows right now

for i in range(COUNT):
    presto.set_led_rgb(i, 0, 0, 0)


def mood_colour(mood, t):
    """Target colour of a mood (a hamster state or a scene) t ms into it."""
    wave = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 3000)
    if mood == "sleep":  # dim moonlight, slow breathing
        return (4 + 6 * wave, 4 + 6 * wave, 20 + 30 * wave)
    if mood == "happy":  # pink pulse on every hop
        hop = math.sin(math.pi * ((t % 700) / 700))
        return (60 + 140 * hop, 10 + 30 * hop, 40 + 70 * hop)
    if mood == "startle":
        return (160, 160, 160) if t < 150 else (40, 30, 10)
    if mood == "ball":  # Claude coral while they play
        return (70 + 15 * wave, 30, 15)
    if mood == "eat":  # cosy warm flicker while munching
        return (90 + 30 * ((t // 150) % 2), 40, 5)
    if mood == "brawl":  # fight cloud: red/white flicker
        return (230, 40, 20) if (t // 90) % 2 else (230, 210, 190)
    if mood == "dance":  # party colours
        return (90 + 90 * math.sin(t / 300), 90 + 90 * math.sin(t / 300 + 2.1), 90 + 90 * math.sin(t / 300 + 4.2))
    if mood == "failed":  # a pipeline is red: slow red pulse
        return (40 + 120 * wave, 0, 8 + 10 * wave)
    if mood == "alert":  # an agent is waiting for you: blink
        return (220, 130, 0) if (t // 400) % 2 == 0 else (15, 8, 0)
    if mood == "done":
        return (15, 80 + 30 * wave, 25)
    return (50 + 15 * wave, 25 + 8 * wave, 4)  # warm amber


FAST = ("happy", "startle", "alert", "brawl", "dance")


def update(mood, t, own=()):
    """All LEDs fade to the colour of `mood` (None: off); `own` gives single
    LEDs their own colour (one per agent), None leaves that LED to the mood."""
    if mood is None:
        target, speed = (0, 0, 0), 0.3
    else:
        target = mood_colour(mood, t)
        speed = 0.5 if mood in FAST else 0.08
    for i in range(3):
        _base[i] += (target[i] - _base[i]) * speed
    base = tuple(int(c) for c in _base)
    for i in range(COUNT):
        rgb = own[i] if i < len(own) and own[i] else base
        if rgb != _shown[i]:
            presto.set_led_rgb(i, *rgb)
            _shown[i] = rgb


def agent_colours(now):
    """One LED per agent that isn't idle: steady blue = working, green =
    done, blinking orange = waiting for you (the only one that blinks)."""
    out = []
    for a in herdr.agent_list[:COUNT]:
        s = a.get("s")
        if s == "working":
            out.append((20, 60, 170))
        elif s == "done":
            out.append((0, 170, 50))
        elif s == "blocked":
            out.append((230, 140, 0) if (now // 400) % 2 == 0 else (20, 10, 0))
        else:
            out.append(None)
    return out
