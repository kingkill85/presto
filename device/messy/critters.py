# Little animals passing through the scene:
#   a bird flies by every few minutes; now and then it lands on Clawd's head
#   and flies off as soon as he moves or does something else
#   a snail crawls across the meadow very slowly (a few minutes); when Messy
#   comes close it pulls back into its shell and Messy sniffs at it

import math
import random
import time

from messy.gfx import WIDTH, draw_colour_art, pen
from messy.sprites import C_BASE_Y, CS, GROUND, S

BODY_PEN = pen((150, 105, 70))
BELLY_PEN = pen((230, 210, 180))
WING_PEN = pen((105, 72, 48))
BEAK_PEN = pen((255, 163, 0))
EYE_PEN = pen((0, 0, 0))
SNAIL_PEN = pen((170, 182, 120))
SHELL_PEN = pen((190, 115, 60))
SHELL_DARK_PEN = pen((125, 70, 40))

CALM = ("idle", "look", "think", "sleep", "work", "sad")  # Clawd holds still enough for a bird
SNAIL_SPEED = 0.07  # px per 66 ms: about one pixel a second

bird = None  # {"phase": fly/sit/leave, "x", "y", "vx", "vy", "land", "t0", "stay", "sx"}
snail = None  # {"x", "hidden_until"}
_next_bird = time.ticks_add(time.ticks_ms(), random.randint(60000, 150000))
_next_snail = time.ticks_add(time.ticks_ms(), random.randint(180000, 480000))


def update(now, k, messy, clawd, cp, night):
    """night: birds sleep too."""
    _update_bird(now, k, clawd, cp, night)
    _update_snail(now, k, messy)


def _update_bird(now, k, clawd, cp, night):
    global bird, _next_bird
    if bird is None:
        if time.ticks_diff(now, _next_bird) > 0 and not night:
            _next_bird = time.ticks_add(now, random.randint(120000, 300000))
            right = random.random() < 0.5
            bird = {"phase": "fly", "x": WIDTH + 6 if right else -12, "y": random.randint(40, 90),
                    "vx": -1.8 if right else 1.8, "vy": 0, "t0": now,
                    "land": clawd.state in CALM and random.random() < 0.7}
        return
    b = bird
    head_x, head_y = clawd.x + cp.dx + 8 * CS, C_BASE_Y - cp.jump + cp.bob * CS - 12
    if b["phase"] == "fly":
        if b["land"] and clawd.state in CALM:  # glide down to his head
            dx, dy = head_x - b["x"], head_y - b["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            step = 2.2 * k
            if dist <= step:
                b.update(phase="sit", x=head_x, y=head_y, t0=now, sx=clawd.x, stay=random.randint(6000, 15000))
            else:
                b["x"] += dx / dist * step
                b["y"] += dy / dist * step
                b["vx"] = 1 if dx > 0 else -1
        else:
            b["x"] += b["vx"] * k
            b["y"] += 0.6 * math.sin(time.ticks_diff(now, b["t0"]) / 200) * k
            if b["x"] < -20 or b["x"] > WIDTH + 20:
                bird = None
    elif b["phase"] == "sit":
        b["x"], b["y"] = head_x, head_y
        if (clawd.state not in CALM or clawd.x != b["sx"] or cp.jump
                or time.ticks_diff(now, b["t0"]) > b["stay"]):
            b.update(phase="leave", vx=random.choice((-2.2, 2.2)), vy=-2.0)
    else:  # leave: up and away
        b["x"] += b["vx"] * k
        b["y"] += b["vy"] * k
        if b["y"] < -12 or b["x"] < -20 or b["x"] > WIDTH + 20:
            bird = None


def _update_snail(now, k, messy):
    global snail, _next_snail
    if snail is None:
        if time.ticks_diff(now, _next_snail) > 0:
            _next_snail = time.ticks_add(now, random.randint(600000, 1200000))
            snail = {"x": WIDTH + 2, "hidden_until": now}
        return
    if near_messy(messy):
        snail["hidden_until"] = time.ticks_add(now, 6000)
    if time.ticks_diff(now, snail["hidden_until"]) >= 0:
        snail["x"] -= SNAIL_SPEED * k
        if snail["x"] < -32:
            snail = None


def near_messy(messy):
    return snail is not None and abs(messy.x + 8 * S - snail["x"] - 14) < 34 and messy.state in ("idle", "look", "walk")


def react(messy, hp):
    """Messy sniffs at the snail when it's right next to him."""
    if near_messy(messy):
        hp.sniff = True
        hp.look = -1 if snail["x"] + 14 < messy.x + 8 * S else 1


# 4 px pixel art; t tail, b body, B belly, w wing, e eye, k beak / g foot,
# s shell, S its spiral
BIRD = {
    "up": ("..w...", "..wbe.", "tbbbbk", ".BBB.."),
    "down": ("......", "...be.", "tbwbbk", ".BwB.."),
    "folded": ("......", "...be.", "twwbbk", ".BBB.."),
}
BIRD_LEFT = {k: tuple("".join(reversed(row)) for row in v) for k, v in BIRD.items()}  # no [::-1] in MicroPython
BIRD_PENS = {"t": WING_PEN, "b": BODY_PEN, "B": BELLY_PEN, "w": WING_PEN, "e": EYE_PEN, "k": BEAK_PEN}
SNAIL = (("g.g.ss.", "g.gsSSs", ".ggsSss", "ggggggg"), ("g.g.ss.", "g.gsSSs", "gg.sSss", ".gggggg"))
SHELL = ("....ss.", "...sSSs", "...sSss", "...ssss")
SNAIL_PENS = {"g": SNAIL_PEN, "s": SHELL_PEN, "S": SHELL_DARK_PEN}


def draw(now):
    if snail:
        hidden = time.ticks_diff(now, snail["hidden_until"]) < 0
        art = SHELL if hidden else SNAIL[(now // 700) % 2]
        draw_colour_art(art, SNAIL_PENS, snail["x"], GROUND - 4 * 4 + 4)
    if bird:
        b = bird
        if b["phase"] == "sit":
            wings = "folded"
        else:
            wings = "up" if (time.ticks_diff(now, b["t0"]) // 120) % 2 else "down"
        art = (BIRD if b["vx"] > 0 else BIRD_LEFT)[wings]
        draw_colour_art(art, BIRD_PENS, b["x"] - 12, b["y"] - 4)
