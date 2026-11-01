# The characters: Messy the hamster, Clawd (the Claude Code mascot) and the
# pirate, plus the umbrellas they hold in the rain. Where they stand on screen
# lives here too.

from messy.gfx import (COLOURS, CLAWD_PEN, EYE_PEN, HANDLE_PEN, HAT_PEN, LAPTOP_EDGE_PEN, LAPTOP_PEN, LEAF_DARK_PEN,
                       LEAF_PEN, UMBRELLA_PEN, UMBRELLA_TIP_PEN, WIDTH, WOOL_PEN, blit, display, draw_art, pen,
                       runs_from_grid)

GROUND = 206  # y of the ground line

# --- Messy -------------------------------------------------------------------

S = 4  # size of one hamster pixel
BASE_Y = GROUND - 14 * S  # sprite top when standing: 13 body rows + feet row
MIN_X, MAX_X = 4, 60  # the hamster lives on the left, Clawd on the right
HOME_X = 20

# 16x13, eyes are drawn separately
BODY = (
    "..##........##..",
    ".#pp#......#pp#.",
    ".#p##########p#.",
    "..############..",
    ".##############.",
    "################",
    "################",
    "##oooooppooooo##",
    "#oooooooooooooo#",
    "#oooooooooooooo#",
    "##oooooooooooo##",
    ".##oooooooooo##.",
    "..############..",
)
BODY_PIXELS = [(c, r, ch) for r, row in enumerate(BODY) for c, ch in enumerate(row) if ch != "."]

EYES = {
    "open": ((4, 5), (4, 6), (11, 5), (11, 6)),
    "closed": ((3, 6), (4, 6), (11, 6), (12, 6)),
    "happy": ((3, 6), (4, 5), (5, 6), (10, 6), (11, 5), (12, 6)),
    "wide": ((4, 5), (5, 5), (4, 6), (5, 6), (10, 5), (11, 5), (10, 6), (11, 6)),
    "angry": ((3, 5), (4, 6), (5, 6), (12, 5), (11, 6), (10, 6)),
}
SEED = ("ee", "eo", "ee")

_hamster_cache = {}


def hamster_sprite(eyes, look, step, bob, puff, paws, mouth, blush, seed, ear, sniff, wear):
    key = (eyes, look, step, bob, puff, paws, mouth, blush, seed, ear, sniff, wear)
    runs = _hamster_cache.get(key)
    if runs is not None:
        return runs
    g = [["."] * 18 for _ in range(14)]  # cols -1..16

    def put(c, r, ch):
        if 0 <= r < 14 and -1 <= c <= 16:
            g[r][c + 1] = ch

    for c, r, ch in BODY_PIXELS:
        put(c, r + bob, ch)
    if ear:  # left ear flicks outwards
        put(2, bob, ".")
        put(3, bob, ".")
        put(1, bob, "#")
        put(2, bob, "#")
    if sniff:  # nose twitches up
        put(7, 7 + bob, "o")
        put(8, 7 + bob, "o")
        put(7, 6 + bob, "p")
        put(8, 6 + bob, "p")
    for c, r in EYES[eyes]:
        put(c + (look if eyes == "open" else 0), r + bob, "e")
    if blush:
        put(2, 7 + bob, "p")
        put(13, 7 + bob, "p")
    if mouth:
        put(6 + mouth, 8 + bob, "e")
    for r in range(8, 9 + puff) if puff else ():  # full cheeks bulge out
        put(-1, r + bob, "#")
        put(16, r + bob, "#")
        put(0, r + bob, "o")
        put(15, r + bob, "o")
    if seed:
        for r, row in enumerate(SEED):
            for c, ch in enumerate(row):
                put(7 + c, 9 + r + bob, ch)
    if "hat" in wear:  # beanie with a bobble instead of the ears
        for r in range(3):
            for c in range(-1, 17):
                put(c, r + bob, ".")
        put(7, bob, "o")
        put(8, bob, "o")
        for c in range(4, 12):
            put(c, 1 + bob, "r" if c % 3 else "R")
        for c in range(3, 13):
            put(c, 2 + bob, "r")
        for c in range(2, 14):
            put(c, 3 + bob, "o")
    if "shades" in wear:
        for c in (3, 4, 5, 10, 11, 12):
            put(c, 5 + bob, "e")
            put(c, 6 + bob, "e")
        for c in range(6, 10):
            put(c, 5 + bob, "e")
    for c, r in paws:
        put(c, r + bob, "p")
    # Feet: step 1 lifts the left one, step 2 the right one
    for c in (3, 4):
        put(c, 12 if step == 1 else 13, "p")
    for c in (11, 12):
        put(c, 12 if step == 2 else 13, "p")
    runs = runs_from_grid(g, COLOURS, 1)
    if len(_hamster_cache) > 200:
        _hamster_cache.clear()
    _hamster_cache[key] = runs
    return runs


def draw_hamster(x, y, p, wear):
    """Messy at (x, y) in pose p (see actors.Pose)."""
    blit(hamster_sprite(p.eyes, p.look, p.step, p.bob, p.puff, p.paws, p.mouth, p.blush, p.seed, p.ear, p.sniff,
                        wear), x, y, S)


LEAF_ART = ("....######....", "..##########..", ".############.", "######..######")


def draw_leaf_umbrella(x, y):
    """Big leaf held up by the hamster's right paw (13, 7)."""
    x, y = int(x), int(y)
    draw_art(LEAF_ART, x + 5 * S, y - 7 * S, S, LEAF_PEN)
    display.set_pen(LEAF_DARK_PEN)
    display.rectangle(x + 13 * S, y - 4 * S, S, 11 * S)


# --- Clawd -------------------------------------------------------------------
# After the Claude Code logo (" ▐▛███▜▌ / ▝▜█████▛▘ / ▘▘ ▝▝") with every block
# quadrant as one pixel, doubled in height: 16x10, a 12x8 body with arms on
# rows 4-5, four legs on rows 8-9. Simple enough to draw with rectangles.

CS = 5  # size of one Clawd pixel
C_BASE_Y = GROUND - 10 * CS
C_MIN_X = 124
C_MAX_X = WIDTH - 16 * CS - 4
C_HOME_X = 140

CLAWD_EYES = {  # (col, row, w, h)
    "open": ((4, 2, 1, 2), (11, 2, 1, 2)),
    "closed": ((3, 3, 2, 1), (11, 3, 2, 1)),
    "happy": ((3, 3, 1, 1), (4, 2, 1, 1), (5, 3, 1, 1), (10, 3, 1, 1), (11, 2, 1, 1), (12, 3, 1, 1)),
    "wide": ((4, 2, 2, 2), (10, 2, 2, 2)),
    "sad": ((4, 3, 1, 1), (11, 3, 1, 1)),
    "down": ((4, 3, 1, 1), (11, 3, 1, 1)),
    "angry": ((3, 1, 1, 1), (4, 2, 1, 2), (12, 1, 1, 1), (11, 2, 1, 2)),
}


def draw_clawd(x, y, p, wear):
    """Clawd at (x, y) in pose p. p.arms: per side True (up), False (down) or
    a row number."""
    x, y = int(x), int(y)
    bob = p.bob

    def px(c, r, w=1, h=1):
        display.rectangle(x + c * CS, y + r * CS, w * CS, h * CS)

    display.set_pen(CLAWD_PEN)
    px(2, bob, 12, 8)
    for side, a in zip((0, 14), p.arms):
        px(side, (2 if a is True else 4 if a is False else a) + bob, 2, 2)
    # Legs: step 1 lifts the outer pair, step 2 the inner pair; bob squashes them
    for i, c in enumerate((3, 5, 10, 12)):
        if bob:
            px(c, 9)
        else:
            px(c, 8, 1, 1 if p.step == 1 + (i in (1, 2)) else 2)
    display.set_pen(EYE_PEN)
    for c, r, w, h in CLAWD_EYES[p.eyes]:
        px(c + (p.look if p.eyes == "open" else 0), r + bob, w, h)
    if "hat" in wear:
        display.set_pen(HAT_PEN)
        px(4, bob - 2, 8, 1)
        px(3, bob - 1, 10, 1)
        display.set_pen(WOOL_PEN)
        px(2, bob, 12, 1)
        px(7, bob - 3, 2, 1)
    if "shades" in wear:
        display.set_pen(EYE_PEN)
        px(3, 2 + bob, 3, 2)
        px(10, 2 + bob, 3, 2)
        px(6, 2 + bob, 4, 1)
    if p.laptop:  # lid facing us, keyboard base in front of the legs
        display.set_pen(LAPTOP_PEN)
        px(4, 4, 8, 4)
        display.set_pen(LAPTOP_EDGE_PEN)
        px(3, 8, 10, 1)
        px(7, 5, 2, 2)  # logo


UMBRELLA_ART = ("......######......", "...############...", ".################.", "##################")


def draw_umbrella(x, y):
    """Red umbrella held up by Clawd's raised left arm (col 1)."""
    x, y = int(x), int(y)
    draw_art(UMBRELLA_ART, x - CS, y - 10 * CS, CS, UMBRELLA_PEN)
    display.set_pen(UMBRELLA_TIP_PEN)
    display.rectangle(x + 7 * CS, y - 11 * CS, 2 * CS, CS)
    display.set_pen(HANDLE_PEN)
    display.rectangle(x + CS, y - 6 * CS, CS, 8 * CS)


# --- the pirate ----------------------------------------------------------------
# Guybrush fan art in the style of Monkey Island 2 (beard, long marine coat,
# bandolier and belt), facing right. 16 wide: 25 rows of body plus 7 rows of
# legs; a dark outline is added around the whole figure when a pose is built.

GB = 4  # size of one pirate pixel
GB_W = 16
GB_Y = GROUND - 32 * GB
GB_OFF = 3  # grid columns left of col 0 (arms and outline reach out to -2 / 17)
GB_COLOURS = {  # Monkey Island 2 look: beard, marine coat, black trousers
    "H": pen((255, 240, 170)),  # hair highlight
    "y": pen((240, 200, 90)),   # hair
    "Y": pen((190, 140, 50)),   # hair shade
    "z": pen((170, 115, 50)),   # beard
    "k": pen((235, 180, 140)),  # skin
    "K": pen((190, 130, 100)),  # skin shade
    "w": pen((240, 235, 220)),  # shirt, eye white
    "L": pen((75, 100, 170)),   # coat light edge
    "c": pen((40, 60, 120)),    # marine blue coat
    "C": pen((25, 35, 80)),     # coat shade, far sleeve
    "g": pen((230, 180, 40)),   # gold buttons, buckle
    "b": pen((110, 60, 30)),    # belts
    "n": pen((30, 26, 36)),     # trousers, far leg
    "N": pen((62, 56, 74)),     # near leg
    "d": pen((80, 45, 25)),     # boots
    "e": pen((20, 15, 20)),     # eye, mouth
    # selective outline: a darker shade of whatever it borders
    "j": pen((125, 85, 30)),    # around hair and beard
    "q": pen((150, 95, 70)),    # around skin
    "v": pen((14, 20, 52)),     # around the coat
    "O": pen((12, 8, 18)),      # around trousers
    "D": pen((48, 26, 14)),     # around boots
}
OUTLINE_OF = {"H": "j", "y": "j", "Y": "j", "z": "j", "k": "q", "K": "q", "w": "v", "L": "v", "c": "v",
              "C": "v", "g": "v", "b": "v", "n": "O", "N": "O", "d": "D", "e": "O"}
GB_BODY = (
    "......yyyy......",
    "....yyHHHyy.....",
    "...yyyyyyyyyy...",
    "..yYyyyyyyyyy...",
    "..Yyyyyykkkkk...",
    "..YYyyykkkkkk...",
    "..bYyyKkkwekkk..",
    ".yY.yyKkkkkkkkk.",
    ".yY..zkkkkkKkk..",
    ".Yy..zzkkkzzk...",
    ".yY..zzzzzzzz...",
    "..Y...zzzzzz....",
    "..y....kkk......",
    "...Y.cCwwwCc....",
    "....Lccwwwccc...",
    "...CLcccwccbcC..",
    "...CLcccccbccC..",
    "...CLccccbcgcC..",
    "...CLcccbccccC..",
    "...CLccbcccgcC..",
    "...CLcbccccccC..",
    "...CbbbbgbbbbC..",
    "...kLcccccccck..",
    "...CLcccc.ccccC.",
    "..CLccc....cccC.",
)
# Walk cycle: a (far leg back), pass, b (far leg forward), pass
GB_LEGS = {
    "stand": (".....nn..NN.....", ".....nn..NN.....", ".....nn..NN.....", ".....nn..NN.....",
              ".....dd..dd.....", "....ddd..ddd....", "....dddd.dddd..."),
    "a": ("......nNN.......", ".....nn..NN.....", "....nn....NN....", "...nn......NN...",
          "...dd.......dd..", "..ddd.......ddd.", "..dddd......dddd"),
    "pass": ("......nNN.......", "......nNN.......", "......nNN.......", "......nNN.......",
             "......ddd.......", ".....dddd.......", ".....ddddd......"),
    "b": ("......NNn.......", ".....NN..nn.....", "....NN....nn....", "...NN......nn...",
          "...dd.......dd..", "..ddd.......ddd.", "..dddd......dddd"),
}
# Arm swing while walking: lower sleeves (rows 19-22) of the far arm (col 3)
# and the near arm (col 13) swing back and forth
GB_SWING = {
    "a": ((2, 19, "C"), (2, 20, "C"), (1, 21, "C"), (1, 22, "k"),
          (14, 19, "c"), (14, 20, "c"), (15, 21, "c"), (15, 22, "k")),
    "b": ((12, 19, "c"), (11, 20, "c"), (11, 21, "c"), (10, 22, "k")),
}
GB_WALK = (("a", "a", 0), ("pass", "down", -2), ("b", "b", 0), ("pass", "down", -2))  # legs, arms, bob
# Arms thrown up in a V: the sleeves (cols 3 and 13, rows 14-22) move up here
GB_ARMS_UP = (
    (2, 13, "C"), (3, 13, "c"), (1, 12, "C"), (2, 12, "c"), (0, 11, "C"), (1, 11, "c"),
    (-1, 10, "C"), (0, 10, "c"), (-1, 9, "k"), (0, 9, "k"), (-1, 8, "k"), (0, 8, "k"),
    (12, 13, "c"), (13, 13, "C"), (13, 12, "c"), (14, 12, "C"), (14, 11, "c"), (15, 11, "C"),
    (15, 10, "c"), (16, 10, "C"), (15, 9, "k"), (16, 9, "k"), (15, 8, "k"), (16, 8, "k"),
)
GB_MOUTH = (11, 10)

_gb_cache = {}


def guybrush_sprite(flip, legs, arms, mouth):
    key = (flip, legs, arms, mouth)
    runs = _gb_cache.get(key)
    if runs is not None:
        return runs
    cols = GB_W + 2 * GB_OFF
    g = [["."] * cols for _ in range(32)]

    def put(c, r, ch):
        if 0 <= r < 32 and 0 <= c + GB_OFF < cols:
            g[r][c + GB_OFF] = ch

    for r, row in enumerate(GB_BODY + GB_LEGS[legs]):
        for c, ch in enumerate(row):
            if ch != ".":
                put(c, r, ch)
    if arms == "up":
        for r in range(14, 23):
            put(3, r, ".")
            put(13, r, ".")
        put(4, 22, "L")  # coat edge where the hand was
        for c, r, ch in GB_ARMS_UP:
            put(c, r, ch)
    elif arms in GB_SWING:
        for r in range(19, 23):
            put(3, r, ".")
            put(13, r, ".")
        for c, r, ch in GB_SWING[arms]:
            put(c, r, ch)
    if mouth:
        put(GB_MOUTH[0], GB_MOUTH[1], "e")
    # selective outline: each outline pixel is a dark shade of its neighbour
    src = [row[:] for row in g]
    for r in range(32):
        for c in range(cols):
            if src[r][c] != ".":
                continue
            for rr, cc in ((r, c - 1), (r, c + 1), (r + 1, c), (r - 1, c)):
                if 0 <= rr < 32 and 0 <= cc < cols and src[rr][cc] != ".":
                    g[r][c] = OUTLINE_OF.get(src[rr][cc], "O")
                    break
    if flip:
        for row in g:
            row.reverse()
    # unflipped: draw col = index - GB_OFF; flipped: index j shows col GB_W-1-c
    # with c = cols-1-j-GB_OFF, which works out to the same offset
    runs = runs_from_grid(g, GB_COLOURS, GB_OFF)
    _gb_cache[key] = runs
    return runs


def draw_guybrush(gx, flip=False, legs="stand", arms="down", mouth=False, bob=0):
    blit(guybrush_sprite(flip, legs, arms, mouth), gx, GB_Y + bob, GB)
