# Beeps and tunes on the buzzer. Notes are (start Hz, end Hz, ms, volume); the
# pitch slides from start to end, 0 is a pause. A 10 ms timer plays them in the
# background so drawing never waits.

import machine
from presto import Buzzer

from messy.prefs import settings

CHARACTER_SOUNDS = False  # squeaks and munching; too much for a desk, so off
VOLUME = 0.1  # PWM duty, 0.5 is the loudest
MUSIC_VOLUME = 0.08

SOUNDS = {  # (start Hz, end Hz, ms)
    "squeak": ((1800, 2600, 60), (0, 0, 40), (2000, 3200, 80)),
    "startle": ((1400, 3400, 120), (0, 0, 30), (3000, 2600, 40)),
    "whistle": ((2600, 1200, 800),),
    "catch": ((900, 1500, 40),),
    "munch": ((420, 300, 25),),
    "yum": ((1200, 1600, 70), (0, 0, 30), (1500, 2100, 90)),
    "yawn": ((900, 1100, 120), (1100, 450, 450)),
    "snore": ((160, 130, 280),),
    "step": ((3500, 3500, 6),),
    "toss": ((600, 1400, 60),),
    # pipelines: two rising beeps, a happy run up, a sad trombone
    "pipe_start": ((880, 880, 70), (0, 0, 50), (1175, 1175, 90)),
    "pipe_ok": ((784, 784, 90), (0, 0, 20), (988, 988, 90), (0, 0, 20), (1175, 1175, 90), (0, 0, 20),
                (1568, 1568, 240)),
    "pipe_fail": ((523, 523, 180), (0, 0, 40), (494, 494, 180), (0, 0, 40), (466, 466, 180), (0, 0, 40),
                  (440, 440, 160), (415, 370, 520)),
    "click": ((1800, 1800, 15),),
    # Claude: a soft ding-dong when it's done, three quick beeps when it needs you
    "agent_done": ((1319, 1319, 80), (0, 0, 30), (1047, 1047, 160)),
    "agent_alert": ((1760, 1760, 60), (0, 0, 60), (1760, 1760, 60), (0, 0, 60), (1760, 1760, 60)),
    # fight: growls, punches, a whoosh when they fly apart, an aww for the hug
    "grr": ((150, 120, 160),),
    "pow": ((320, 70, 70),),
    "bam": ((950, 140, 90),),
    "bonk": ((600, 1300, 40), (1300, 280, 90)),
    "whoosh": ((2200, 500, 220),),
    "aww": ((660, 880, 120), (0, 0, 30), (880, 1047, 180)),
}
PIPE_SOUNDS = ("pipe_start", "pipe_ok", "pipe_fail", "click", "agent_done", "agent_alert")  # SOUNDS switch
FIGHT_SOUNDS = ("grr", "pow", "bam", "bonk", "whoosh", "aww")  # ANIMATION switch (scene sounds)

# Original pirate jingle (not the game's theme): (Hz, ms), 0 is a rest
PIRATE_JINGLE = (
    (392, 150), (523, 300), (523, 150), (587, 150), (659, 150), (698, 150), (784, 450), (0, 150),
    (659, 150), (587, 150), (523, 300), (659, 150), (587, 450), (0, 150),
    (392, 150), (523, 300), (523, 150), (587, 150), (659, 150), (698, 150), (784, 300), (880, 150), (784, 300),
    (698, 150), (659, 150), (587, 300), (494, 150), (523, 600),
)

buzzer = Buzzer(43)
notes = []
note_ms = 0
music_playing = False
on_scene = True  # songs only play while the scene is on screen


def stop_music():
    global notes, music_playing
    if music_playing:
        notes = []
        buzzer.set_tone(0)
        music_playing = False


def play(name, volume=VOLUME):
    global notes, note_ms, music_playing
    if name in PIPE_SOUNDS:
        allowed = settings["sounds"]
    elif name in FIGHT_SOUNDS:
        allowed = settings["anim"]
    else:
        allowed = CHARACTER_SOUNDS
    if not allowed:
        return
    notes = [(f0, f1, ms, volume) for f0, f1, ms in SOUNDS[name]]
    note_ms = 0
    music_playing = False


def play_music(tune):
    """tune: [(Hz, ms), ...]"""
    global notes, note_ms, music_playing
    if not settings["music"] or not on_scene:
        return
    music_playing = True
    notes = []
    for f, ms in tune:  # a short gap between notes so repeated ones are heard
        notes.append((f, f, ms - 25, MUSIC_VOLUME))
        notes.append((0, 0, 25, 0))
    note_ms = 0


# --- RTTTL ringtones -----------------------------------------------------------

RTTTL_NOTES = {"c": 0, "c#": 1, "d": 2, "d#": 3, "e": 4, "f": 5, "f#": 6, "g": 7, "g#": 8, "a": 9, "a#": 10, "b": 11}


def parse_rtttl(text):
    """RTTTL ringtone ("name:d=4,o=5,b=120:8e6,8p,...") to [(Hz, ms), ...]."""
    parts = text.strip().split(":")
    if len(parts) < 3:
        return None
    defaults = {"d": 4, "o": 6, "b": 63}
    for item in parts[1].split(","):
        key, _, value = item.strip().partition("=")
        if key in defaults and value.isdigit():
            defaults[key] = int(value)
    whole = 4 * 60000 // defaults["b"]  # ms of a whole note
    tune = []
    for token in ":".join(parts[2:]).split(","):
        t = token.strip().lower()
        if not t:
            continue
        i = 0
        while i < len(t) and t[i].isdigit():
            i += 1
        dur = int(t[:i]) if i else defaults["d"]
        name = t[i] if i < len(t) else "p"
        i += 1
        if i < len(t) and t[i] == "#":
            name += "#"
            i += 1
        dotted = "." in t[i:]
        digits = "".join(ch for ch in t[i:] if ch.isdigit())
        octave = int(digits) if digits else defaults["o"]
        ms = whole // dur
        if dotted:
            ms += ms // 2
        if name == "p" or name not in RTTTL_NOTES:
            tune.append((0, ms))
        else:
            n = RTTTL_NOTES[name] + 12 * (octave - 4)
            tune.append((int(261.63 * 2 ** (n / 12)), ms))
    return tune or None


def load_rtttl(name):
    """(tune, beat ms) from an RTTTL file on the Presto, or (None, None)."""
    try:
        with open(name) as f:
            text = f.read()
    except OSError:
        return None, None
    tune = parse_rtttl(text)
    bpm = 63
    for item in text.split(":")[1].split(",") if text.count(":") >= 2 else ():
        key, _, value = item.strip().partition("=")
        if key == "b" and value.isdigit():
            bpm = int(value)
    return tune, 60000 // bpm


def guybrush_tune():
    """Your own melody from guybrush.rtttl on the Presto, else the jingle."""
    try:
        with open("guybrush.rtttl") as f:
            return parse_rtttl(f.read()) or PIRATE_JINGLE
    except OSError:
        return PIRATE_JINGLE


def _tick(_):
    global notes, note_ms
    if not notes:
        return
    f0, f1, ms, volume = notes[0]
    if note_ms >= ms:
        notes.pop(0)
        note_ms = 0
        if not notes:
            buzzer.set_tone(0)
        return
    if f0:
        buzzer.set_tone(int(f0 + (f1 - f0) * note_ms / ms), volume)
    else:
        buzzer.set_tone(0)
    note_ms += 10


buzzer.set_tone(0)
timer = machine.Timer(period=10, callback=_tick)
