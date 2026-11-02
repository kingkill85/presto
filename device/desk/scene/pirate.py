# The pirate's visits: now and then (rarely, it should stay special) Guybrush
# walks in and does something with Messy and Clawd. Little nods to the
# Monkey Island games, with our own jokes:
#   buh       he shouts "BUH!" and scares both off (the old visit)
#   treasure  a treasure map, Messy digs, the chest holds... a T-shirt
#   monkey    "look, a three-headed monkey!" and Clawd's coffee is gone
#   fence     a sword fight with Clawd (sabre against fork) and insults
#   spit      a spitting contest, Messy wins with a seed from his cheeks
# Except for "buh" he introduces himself first, and like in the games
# nobody gets his name right: Messy or Clawd says it wrong, he corrects them,
# and they get it wrong again when he leaves.
#
# Like the other directors: update() moves everyone and poses them (False when
# over), draw() adds the pirate, his props and the speech bubbles.

import math
import random
import time

from desk import sound
from desk.gfx import BALL_PEN, EYE_PEN, SEED_ART, SEED_PEN, WIDTH, display, draw_art, draw_colour_art, pen
from desk.scene.actors import RUN, WALK
from desk.scene.directors import arc, walk_to
from desk.scene.particles import spawn
from desk.scene.scene import MUG, PROP_PENS
from desk.scene.sprites import (BASE_Y, C_BASE_Y, C_HOME_X, C_MAX_X, CS, GB, GB_W, GB_Y, GROUND, HOME_X, S,
                                draw_guybrush, walk_frame)

KINDS = (("buh", 2), ("treasure", 3), ("monkey", 3), ("fence", 3), ("spit", 3))  # (kind, weight)
FIRST_MS = (10 * 60000, 20 * 60000)  # after a start
EVERY_MS = (30 * 60000, 60 * 60000)  # between visits: rare, so it stays special

OFF_L = -GB_W * GB - 12  # off the screen on the left
G_STOP = 4  # where he stands
BACK_X = 76  # Messy steps back to here when he comes in
HAND = 13 * GB  # his near hand, from his corner (facing right)
HAND_Y = GB_Y + 22 * GB
TALK = (1, 2, 1, 0, 2, 1, 0, 0)  # mouth while talking

_next_visit = time.ticks_add(time.ticks_ms(), random.randint(*FIRST_MS))
_last_kind = None


def visit_due(now):
    return time.ticks_diff(now, _next_visit) > 0


def pick_kind():
    kinds = [(k, w) for k, w in KINDS if k != _last_kind]
    r = random.uniform(0, sum(w for _, w in kinds))
    for kind, w in kinds:
        r -= w
        if r <= 0:
            return kind
    return kind


# --- props: 4 px pixel art ------------------------------------------------------------

PIRATE_PENS = {
    "p": pen((240, 220, 160)), "l": pen((180, 140, 90)), "r": pen((220, 30, 50)),  # map
    "B": pen((90, 50, 25)), "b": pen((140, 85, 40)), "g": pen((230, 180, 40)), "y": pen((255, 236, 39)),  # chest
    "w": pen((245, 245, 240)), "u": pen((190, 195, 210)), "e": pen((20, 15, 20)),  # shirt
    "s": pen((200, 205, 215)), "h": pen((110, 60, 30)),  # blades, handles
}
MAP = ("ppppppp", "plpprpr", "pllpprp", "pplprpr", "ppppppp")
CHEST = (".BBBBB.", "BbbbbbB", "ggggggg", "BbbgbbB", "BbbbbbB")
CHEST_OPEN = ("BbbbbbB", "BBBBBBB", "BywywyB", "ggggggg", "BbbbbbB", "BbbbbbB")
TSHIRT = ("www...www", "wwwwuwwww", "wwwwwwwww", ".wwwrwww.", "..wewew..", "..wwwww..", "..wwwww..")
SWORD = (".g.....", "hgsssss", ".g.....")  # pointing right
SWORD_L = (".....g.", "sssssgh", ".....g.")  # flipped
FORK = ("sss....", "..s....", "ssshhhh", "..s....", "sss....")  # tines to the left
FLAG = ("dxx", "dxx", "d..", "d..", "d..")
FLAG_PENS = tuple({"d": pen((110, 70, 40)), "x": pen(rgb)} for rgb in ((40, 60, 120), (217, 119, 87), (255, 236, 39)))
SPIT_PEN = pen((200, 230, 255))

# Insults while fencing (our own lines): (Guybrush, Clawd's comeback)
INSULTS = (
    ("ICH HAB SCHON\nKRAKEN BESIEGT!", "MIT DEINEM\nMUNDGERUCH?"),
    ("MEINE KLINGE IST\nGEFUERCHTET!", "DEINE FRISUR\nAUCH!"),
    ("GLEICH BIST DU\nFISCHFUTTER!", "ERST MUSST DU\nMICH TREFFEN!"),
    ("ICH BIN DER\nSCHRECKEN\nDER MEERE!", "DIE MEERE HABEN\nANGST? VOR DIR?"),
    ("DEIN CODE HAT\nNUR BUGS!", "UND DEIN SCHIFF\nNUR LOECHER!"),
    ("ICH HABE DREI\nPRUEFUNGEN\nBESTANDEN!", "UND WIE VIELE\nDUSCHEN?"),
)
HAMSTER_INSULT = ("DU FICHTST WIE\nEIN HAMSTER!", "WIE PASSEND!\nDU RIECHST\nNACH GROG!")  # Messy is offended
# Nobody gets his name right
WRONG_NAMES = ("GUYBUSH", "GREYBRUSH", "GUYBRUST", "KAIBRUSH", "BUYGRUSH", "GUYBURSCH", "GUYBRASH", "TREEPWOOD")
ASK = ("%s WER?", "%s?", "AH, %s!", "HALLO %s!")
CORRECT = ("GUYBRUSH!", "ES HEISST\nGUYBRUSH!", "SEUFZ.", "GUY-BRUSH!\nTHREEPWOOD!", "...")
BYE = ("TSCHUESS,\n%s!", "MACHS GUT,\n%s!", "AHOI,\n%s!")
INTRO = ("EIN MAECHTIGER\nPIRAT!", "UND ICH WILL\nPIRAT WERDEN!", "ICH KANN ZEHN\nMINUTEN LUFT\nANHALTEN!")
LEAVING = ("ICH MUSS LOS,\nDAS GEHEIMNIS\nVON MONKEY ISLAND\nSUCHEN!", "LECHUCK WARTET\nNICHT EWIG!",
           "HAT JEMAND EIN\nGUMMIHUHN\nGESEHEN?")


def say(text, x, y):
    """A speech bubble with one or more lines, kept on the screen; x is
    where the tail points to, y the bubble's bottom."""
    lines = text.split("\n")
    scale = 2
    w = max(display.measure_text(line, 2) for line in lines)
    if w > WIDTH - 20:
        scale, w = 1, max(display.measure_text(line, 1) for line in lines)
    lh = 8 * scale + 1
    h = lh * len(lines) + 6
    bx = max(2, min(int(x) - 12, WIDTH - w - 10))
    by = max(2, int(y) - h)
    display.set_pen(BALL_PEN)
    display.rectangle(bx, by, w + 8, h)
    tx = max(bx + 4, min(int(x), bx + w))
    display.rectangle(tx, by + h, 4, 4)
    display.set_pen(EYE_PEN)
    for i, line in enumerate(lines):
        display.text(line, bx + 4, by + 4 + i * lh, -1, scale)


class Visit:
    interruptible = False

    def __init__(self, messy, clawd, now, kind=None):
        global _last_kind
        self.m, self.c = messy, clawd
        self.kind = kind or pick_kind()
        _last_kind = self.kind
        self.now, self.k, self.t = now, 1, 0
        self.phase, self.t0 = "enter", now
        self.gx = OFF_L
        self.spawned = -100000
        names = list(WRONG_NAMES)  # two different wrong names: hello and goodbye
        self.name1 = names.pop(random.randrange(len(names)))
        self.name2 = random.choice(names)
        self.asker = random.choice("mc")  # who says it wrong
        self.ask = random.choice(ASK) % self.name1
        self.correct = random.choice(CORRECT)
        self.bye = random.choice(BYE) % self.name2
        self.intro_line = random.choice(INTRO)
        self.leaving = random.choice(LEAVING)
        self.items = []  # set by the scenes: (art, pens, x, y) for draw()
        self.flags = []  # (x, colour index) planted in the spitting contest
        self.blob = None  # something flying: [x0, y0, x1, start ms, ms, height, kind]
        self.fallen = None  # the dropped sabre
        self.bubbles = []
        self.g_pose()
        if self.kind == "fence":
            pairs = list(INSULTS)
            first = pairs.pop(random.randrange(len(pairs)))
            self.insults = (first, pairs[random.randrange(len(pairs))], HAMSTER_INSULT)
        sound.play_music(sound.guybrush_tune())
        messy.start("event")
        clawd.start("event")

    # --- helpers -----------------------------------------------------------------

    def go(self, phase):
        self.phase, self.t0, self.t = phase, self.now, 0
        self.spawned = -100000

    def every(self, ms):
        if self.t - self.spawned >= ms:
            self.spawned = self.t
            return True
        return False

    def g_pose(self, **kw):
        self.g = dict(flip=False, legs="stand", arms="down", mouth=0, bob=0, hem=0, hair=0, front=False)
        self.g.update(kw)

    def g_walk(self, target, speed=2.5, ms_per_step=1):
        """Walk the pirate towards target; True once there."""
        self.gx, there = walk_to(self.gx, target, speed, self.k)
        if not there:
            legs, arms, bob, hem, hair = walk_frame(int(self.t * ms_per_step))
            self.g_pose(flip=target < self.gx, legs=legs, arms=arms, bob=bob, hem=hem, hair=hair)
        return there

    def g_talk(self, front=True, **kw):
        self.g_pose(front=front, mouth=TALK[(self.t // 140) % len(TALK)], **kw)

    def g_say(self, text):
        self.bubbles.append((text, self.gx + 44, GB_Y - 4))

    def m_say(self, text):
        self.bubbles.append((text, self.m.x + 30, BASE_Y - 6))

    def c_say(self, text):
        self.bubbles.append((text, self.c.x + 30, C_BASE_Y - 8))

    def move(self, actor, target, speed, p, ms=110):
        actor.x, there = walk_to(actor.x, target, speed, self.k)
        if not there:
            p.step, p.jump = WALK[(self.t // ms) % 4]
            p.look = 1 if target > actor.x else -1
        return there

    def fly(self, x0, y0, x1, ms, height, kind):
        self.blob = [x0, y0, x1, self.t, ms, height, kind]

    def blob_pos(self):
        x0, y0, x1, start, ms, height, kind = self.blob
        u = min(1.0, (self.t - start) / ms)
        y = y0 + (GROUND - 4 - y0) * u - arc(u, height)
        return x0 + (x1 - x0) * u, y, u >= 1

    # --- the frame ---------------------------------------------------------------

    def update(self, now, k, hp, cp):
        self.now, self.k = now, k
        self.t = time.ticks_diff(now, self.t0)
        self.bubbles, self.items = [], []
        self.g_pose()
        hp.look = cp.look = -1  # watching him
        ph = self.phase
        if self.kind == "buh":
            return self.buh(ph, self.t, hp, cp)
        if ph in ("enter", "intro", "who"):
            self.intro(ph, self.t, hp, cp)
        elif ph == "exit":  # a last word, then off; they wave him goodbye with the wrong name
            if self.t < 2200:
                self.g_talk()
                self.g_say(self.leaving)
            else:
                self.farewell(hp, cp)
                if self.g_walk(OFF_L, 3.0):
                    self.go("home")
        elif ph == "home":
            a = self.move(self.m, HOME_X, 2.5, hp)
            b = self.move(self.c, C_HOME_X, 2.0, cp, 120)
            if a and b:
                return self.end()
        else:
            getattr(self, self.kind)(ph, self.t, hp, cp)
        return True

    def farewell(self, hp, cp):
        """Waving him goodbye, with his name wrong again."""
        if self.asker == "m":
            self.m_say(self.bye)
            hp.paws = ((3, 8),) if (self.t // 250) % 2 else ((3, 9),)
        else:
            self.c_say(self.bye)
            cp.arms = ((self.t // 250) % 2 == 0, cp.arms[1])

    def end(self):
        global _next_visit
        _next_visit = time.ticks_add(self.now, random.randint(*EVERY_MS))
        self.m.start("idle")
        self.c.start("idle")
        return False

    def intro(self, ph, t, hp, cp):
        """He walks in and introduces himself; maybe Clawd gets the name wrong."""
        if ph == "enter":
            there = self.g_walk(G_STOP)
            self.move(self.m, BACK_X, 2.0, hp)
            self.move(self.c, C_MAX_X, 1.2, cp, 120)
            hp.look = cp.look = -1
            if there:
                self.go("intro")
        elif ph == "intro":
            if t < 1900:
                self.g_talk()
                self.g_say("ICH BIN GUYBRUSH\nTHREEPWOOD,")
            elif t < 3800:
                self.g_pose(arms="up", mouth=2, bob=-4 if t < 2000 else 0)
                self.g_say(self.intro_line)
            else:
                self.go("who")
        elif ph == "who":  # wrong, of course
            if t < 1700:
                (self.m_say if self.asker == "m" else self.c_say)(self.ask)
                self.g_pose(front=True)
            elif t < 3200:
                self.g_pose(front=True, mouth=2 if t < 2100 else 0)
                self.g_say(self.correct)
            else:
                self.go(self.first())

    def first(self):
        return {"treasure": "map", "monkey": "point", "fence": "places", "spit": "places"}[self.kind]

    def draw(self, now):
        g = self.g
        if self.kind != "buh" or self.phase in ("enter", "scare", "flee", "laugh", "leave"):
            if self.gx > OFF_L:
                draw_guybrush(self.gx, flip=g["flip"], legs=g["legs"], arms=g["arms"], mouth=g["mouth"],
                              bob=g["bob"], hem=g["hem"], hair=g["hair"], front=g["front"])
        for x, ci in self.flags:
            draw_colour_art(FLAG, FLAG_PENS[ci], x, GROUND - 20)
        if self.fallen is not None:
            draw_colour_art(SWORD, PIRATE_PENS, self.fallen[0], self.fallen[1])
        for art, pens, x, y in self.items:
            draw_colour_art(art, pens, x, y)
        if self.blob:
            x, y, _ = self.blob_pos()
            if self.blob[6] == "seed":
                draw_art(SEED_ART, int(x), int(y), S, SEED_PEN)
            else:
                display.set_pen(SPIT_PEN)
                display.rectangle(int(x) // 4 * 4, int(y) // 4 * 4, 4, 4)
        for text, x, y in self.bubbles:
            say(text, x, y)

    def mood(self, now):
        if self.phase == "scare":
            return "startle", time.ticks_diff(now, self.t0)
        if self.phase == "clash":
            return "brawl", now
        if self.phase in ("cheer", "win", "shirt"):
            return "happy", time.ticks_diff(now, self.t0)
        return None

    # --- buh: the old visit ----------------------------------------------------------

    def buh(self, ph, t, hp, cp):
        """He walks in, shouts BUH!, both flee off the screen, he laughs and
        leaves, they come back."""
        m, c, k = self.m, self.c, self.k
        if ph == "enter":  # he walks in, the two nervously back away to the right
            self.gx += 2.5 * k
            legs, arms, bob, hem, hair = walk_frame(t)
            self.g_pose(legs=legs, arms=arms, bob=bob, hem=hem, hair=hair)
            m.x = min(BACK_X, m.x + 2 * k)
            c.x = min(C_MAX_X, c.x + 1.2 * k)
            if self.gx > -40:
                hp.eyes = cp.eyes = "wide"
            if m.x < BACK_X:
                hp.step, hp.jump = WALK[(t // 110) % 4]
            if c.x < C_MAX_X:
                cp.step, cp.jump = WALK[(t // 120) % 4]
            if self.gx >= G_STOP:
                self.go("scare")
        elif ph == "scare":
            self.g_pose(arms="up", mouth=2, bob=-3 if t < 150 else 0, hair=1 if t < 300 else 0)
            self.bubbles.append(("BUH!", self.gx + 50, GB_Y - 4))
            hp.eyes = cp.eyes = "wide"
            hp.paws = ((3, 8), (12, 8))
            hp.jump = int(20 * math.sin(math.pi * min(1, t / 400)))
            cp.arms = (True, True)
            cp.jump = int(16 * math.sin(math.pi * min(1, max(0, t - 100) / 400)))
            if t > 1300:
                self.go("flee")
        elif ph == "flee":
            m.x += 8 * k
            c.x += 7 * k
            hp.eyes = cp.eyes = "wide"
            hp.look = cp.look = 1
            hp.step, hp.jump = RUN[(t // 70) % 4]
            cp.step, cp.jump = RUN[(t // 70) % 4]
            if m.x > WIDTH + 10 and c.x > WIDTH + 10:
                self.go("laugh")
        elif ph == "laugh":
            beat = (t // 200) % 2 == 0
            self.g_pose(bob=-2 if beat else 0, mouth=2 if beat else 1)  # shoulders shake
            self.bubbles.append(("HAR HAR!", self.gx + 50, GB_Y - 4))
            if t > 1800:
                self.go("leave")
        elif ph == "leave":
            if self.g_walk(OFF_L):
                self.go("pause")
        elif ph == "pause":
            if t > 2000:
                self.go("return")
        elif ph == "return":
            a = self.move(m, HOME_X, 2.5, hp)
            b = self.move(c, C_HOME_X, 2.5, cp, 120)
            hp.look = cp.look = -1
            if a and b:
                return self.end()
        return True

    # --- treasure: map, digging, the chest... a T-shirt -------------------------------

    def treasure(self, ph, t, hp, cp):
        m = self.m
        chest_x = BACK_X + 4
        if ph == "map":  # holds up the map with the X
            self.g_talk(front=False)
            self.items.append((MAP, PIRATE_PENS, self.gx + HAND, HAND_Y - 20))
            self.g_say("EIN SCHATZ!\nGENAU HIER!")
            hp.eyes = "wide"
            if t > 2400:
                self.go("dig")
        elif ph == "dig":  # Messy digs, the dirt flies
            self.g_pose()
            self.items.append((MAP, PIRATE_PENS, self.gx + HAND, HAND_Y - 20))
            a = (t // 120) % 2
            hp.paws = ((5, 11 + a), (10, 12 - a))
            hp.bob = a
            if self.every(140):
                spawn("dirt", m.x + 8 * S + random.randint(-12, 4), GROUND - 2, random.uniform(-2.5, 1),
                      random.uniform(-3.5, -2), 30)
            if t > 2600:
                sound.play("bonk")
                self.go("pop")
        elif ph == "pop":  # the chest jumps out, Messy jumps back
            u = min(1.0, t / 700)
            self.items.append((CHEST, PIRATE_PENS, chest_x, GROUND - 20 - arc(u, 44)))
            hp.eyes = "wide"
            hp.jump = arc(min(1.0, t / 400), 16)
            m.x = min(BACK_X + 36, m.x + 3 * self.k)
            self.g_pose(front=True, mouth=1)
            if t > 1300:
                self.go("open")
        elif ph == "open":  # he opens it: sparkles
            self.g_pose(front=True, mouth=2)
            self.items.append((CHEST_OPEN, PIRATE_PENS, chest_x, GROUND - 24))
            if self.every(180) and t < 1200:
                spawn("spark", chest_x + random.randint(0, 24), GROUND - 34, random.uniform(-1, 1), -1.2, 14)
            hp.eyes = cp.eyes = "happy"
            if t > 1500:
                self.go("shirt")
        elif ph == "shirt":  # ... it's a T-shirt
            self.items.append((CHEST_OPEN, PIRATE_PENS, chest_x, GROUND - 24))
            self.g_pose(arms="up", mouth=1)
            self.items.append((TSHIRT, PIRATE_PENS, self.gx + 14, GB_Y - 26))
            if t < 2200:
                self.bubbles.append(("NUR EIN\nT-SHIRT?!", self.gx + 76, GB_Y + 24))
            else:
                self.c_say("STEHT DIR\nBESTIMMT!")
                hp.eyes = "happy"
                hp.mouth = 1 + (t // 150) % 2  # giggles
            if t > 4000:
                self.go("wear")
        elif ph == "wear":  # puts it on, proud
            self.items.append((CHEST_OPEN, PIRATE_PENS, chest_x, GROUND - 24))
            self.g_pose(front=True, mouth=1, bob=-4 if (t // 300) % 2 else 0)
            self.items.append((TSHIRT, PIRATE_PENS, self.gx + 14, GB_Y + 52))
            self.g_say("ICH FAND DEN\nSCHATZ UND BEKAM\nNUR DIESES\nT-SHIRT!")
            if t > 3000:
                self.go("leave")
        elif ph == "leave":  # off with the chest under his arm, still wearing it
            there = self.g_walk(OFF_L, 2.5)
            self.items.append((TSHIRT, PIRATE_PENS, self.gx + 14, GB_Y + 52))
            self.items.append((CHEST, PIRATE_PENS, self.gx - 8, HAND_Y - 8))
            self.farewell(hp, cp)
            if there:
                self.go("home")
        return True

    # --- monkey: "look, a three-headed monkey!" ----------------------------------------

    def monkey(self, ph, t, hp, cp):
        c = self.c
        mug_c = ("mug", -12, 3 * CS - 2)
        if ph == "point":
            cp.arms, cp.props = (3, False), (mug_c,)
            self.g_pose(arms="up", mouth=2)
            self.g_say("SCHAUT! EIN\nDREIKOEPFIGER\nAFFE!")
            if t > 1200:  # they turn round to look
                hp.look = cp.look = 1
                hp.eyes = cp.eyes = "wide"
            if t > 2600:
                self.go("sneak")
        elif ph == "sneak":  # tiptoes over to Clawd's coffee
            cp.arms, cp.props = (3, False), (mug_c,)
            hp.look = cp.look = 1
            hp.eyes = cp.eyes = "wide"
            if self.every(900):
                spawn("note", self.gx + 40, GB_Y + 10, 0.3, -0.8, 18)  # whistling innocently
            if self.g_walk(c.x - 12 - HAND, 1.4, 0.6):  # his hand at the mug
                self.go("grab")
        elif ph == "grab":
            hp.look = cp.look = 1
            self.g_pose(mouth=1)
            self.items.append((MUG, PROP_PENS, self.gx + HAND, HAND_Y - 8))
            cp.arms = (False, False)
            if t > 500:
                self.go("run")
        elif ph == "run":  # and off he goes
            hp.look = cp.look = 1
            there = self.g_walk(OFF_L, 4.0, 1.5)
            self.items.append((MUG, PROP_PENS, self.gx - 4, HAND_Y - 8))
            if there:
                self.go("turn")
        elif ph == "turn":  # nothing there; and where is the coffee?
            if t < 1600:
                self.m_say("?")
                self.c_say("?")
            elif t < 3400:
                cp.eyes = hp.eyes = "angry"
                cp.arms = (True, True) if (t // 200) % 2 else (False, False)
                self.c_say("MEIN KAFFEE?!")
            else:
                cp.eyes = hp.eyes = "angry"
                self.c_say("HALT, %s!" % self.name2)
            if t > 5200:
                self.go("home")
        return True

    # --- fence: sabre against fork, and insults ----------------------------------------

    def fence(self, ph, t, hp, cp):
        m, c = self.m, self.c
        self.items.append((FORK, PIRATE_PENS, c.x - 7 * 4, C_BASE_Y + 2 * CS - 6))  # in his left claw
        cp.arms = (2, False)
        if ph == "places":  # Messy watches from the side, Clawd comes over with a fork
            a = self.move(m, WIDTH - 16 * S, 2.5, hp)
            b = self.move(c, 84, 2.0, cp, 120)
            self.sword()
            if a and b:
                self.round = 0
                self.go("garde")
        elif ph == "garde":
            self.sword()
            self.g_talk(front=False, arms="down")
            self.g_say("EN GARDE!")
            if t > 1200:
                self.go("clash")
        elif ph == "clash":  # back and forth, sparks fly
            lunge = 4 if (t // 160) % 2 else -4
            self.gx = G_STOP + lunge  # he pushes, Clawd gives way, and back
            c.x = 84 + lunge
            self.sword()
            cp.eyes = "angry"
            if self.every(320):
                spawn("spark", self.gx + HAND + 30, HAND_Y - 8, random.uniform(-1, 1), -1.5, 10)
                sound.play("clang")
            if t > 1200:
                self.gx, c.x = G_STOP, 84
                self.go("insult")
        elif ph == "insult":
            self.sword()
            self.g_talk(front=False)
            self.g_say(self.insults[self.round][0])
            if self.insults[self.round] is HAMSTER_INSULT and t > 1200:
                hp.eyes = "angry"
                self.m_say("HEY!")
            if t > 2200:
                self.go("retort")
        elif ph == "retort":
            self.sword()
            self.c_say(self.insults[self.round][1])
            cp.arms = (2, (t // 250) % 2 == 0)
            self.g_pose(mouth=1, bob=2 if t > 1600 else 0)  # that one hit
            if t > 2200:
                self.round += 1
                self.go("clash" if self.round < len(self.insults) else "defeat")
        elif ph == "defeat":  # the sabre flies out of his hand
            if self.fallen is None:
                self.fallen = [self.gx + HAND, HAND_Y - 4]
                sound.play("whoosh")
            u = min(1.0, t / 600)
            self.fallen[0] = self.gx + HAND + int(20 * u)
            self.fallen[1] = HAND_Y - 4 + int((GROUND - 12 - HAND_Y + 4) * u) - arc(u, 30)
            self.g_pose(front=True, mouth=2)
            self.g_say("VERFLIXT!")
            if t > 1800:
                self.go("cheer")
        elif ph == "cheer":
            self.g_pose(front=True)
            cp.arms = (True, True)
            cp.jump = arc((t % 600) / 600, 14)
            hp.eyes = cp.eyes = "happy"
            hp.jump = arc(((t + 300) % 600) / 600, 12)
            if t > 2000:
                self.fallen = None  # he picks it up again
                self.go("exit")
        return True

    def sword(self):
        self.items.append((SWORD, PIRATE_PENS, self.gx + HAND - 4, HAND_Y - 8))

    # --- spit: a spitting contest -----------------------------------------------------

    def spit(self, ph, t, hp, cp):
        m, c = self.m, self.c
        if ph == "places":
            a = self.move(m, WIDTH - 16 * S, 2.5, hp)
            b = self.move(c, 104, 2.0, cp, 120)
            self.g_say("SPUCK-\nWETTBEWERB!")
            self.g_talk(front=True)
            if a and b and t > 1800:
                self.go("g_spit")
        elif ph == "g_spit":  # waits for the wind, winds up, ptui
            if t < 1800:
                self.g_talk(front=False)
                self.g_say("MOMENT... ICH\nWARTE AUF\nDEN WIND!")
                return True
            t -= 1800
            if t < 700:
                self.g_pose(bob=-4, mouth=0)
            elif self.blob is None:
                self.fly(self.gx + 52, GB_Y + 44, 148, 700, 34, "spit")
                sound.play("ptui")
            if self.blob:
                x, _, landed = self.blob_pos()
                self.g_pose(mouth=1)
                if landed:
                    self.flags.append((int(x) // 4 * 4, 0))
                    self.blob = None
                    self.go("g_aside")
        elif ph == "g_aside":  # steps aside for the next one
            if self.g_walk(-52, 2.5) and t > 600:
                self.go("c_go")
        elif ph == "c_go":
            if self.move(c, 4, 2.5, cp, 120):
                self.go("c_spit")
        elif ph == "c_spit":
            cp.look = 1
            if t < 700:
                cp.arms = (True, True)
                cp.bob = 1
            elif self.blob is None:
                self.fly(c.x + 76, C_BASE_Y + 16, 192, 650, 30, "spit")
                sound.play("ptui")
            if self.blob:
                x, _, landed = self.blob_pos()
                if landed:
                    self.flags.append((int(x) // 4 * 4, 1))
                    self.blob = None
                    self.go("c_back")
        elif ph == "c_back":
            cp.eyes = "happy"
            if self.move(c, 104, 2.5, cp, 120):
                self.go("m_go")
        elif ph == "m_go":
            if self.move(m, 8, 2.5, hp):
                self.go("m_spit")
        elif ph == "m_spit":  # cheeks full of seeds... ptui
            hp.look = 1
            if t < 1200:
                hp.puff = min(2, t // 400)
                hp.eyes = "closed"
            elif self.blob is None:
                self.fly(m.x + 56, BASE_Y + 34, WIDTH - 16, 900, 54, "seed")
                sound.play("ptui")
            if self.blob:
                x, _, landed = self.blob_pos()
                if landed:
                    self.flags.append((WIDTH - 12, 2))
                    self.blob = None
                    sound.play("aww")
                    self.go("win")
        elif ph == "win":
            hp.look = 1
            hp.eyes = "happy"
            hp.jump = arc((t % 500) / 500, 14)
            cp.eyes = "wide"
            if t > 1400:
                self.go("back")
        elif ph == "back":  # Messy back to his place, the pirate comes back
            hp.eyes = "happy"
            a = self.move(m, WIDTH - 16 * S, 2.5, hp)
            if self.g_walk(G_STOP, 2.5) and a:
                self.go("protest")
        elif ph == "protest":  # that doesn't count!
            hp.eyes = "happy"
            self.g_pose(front=True, mouth=2 if t < 2000 else 0)
            if t < 2000:
                self.g_say("DAS WAR\nEIN KERN!")
            else:
                self.c_say("KERNE SIND\nERLAUBT!")
            if t > 3800:
                self.go("exit")
        return True
