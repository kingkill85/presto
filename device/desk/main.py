# The start screen. Its star is Messy, a pixel hamster: a little desk pet in
# the blocky, flat style of the Claude Code mascot. 240x240 (every pixel
# doubled), PICO-8 palette. Messy idles, looks around, walks, eats seeds,
# washes its face and falls asleep.
# Tap Messy (or Clawd) to make it happy, wake it up and see its name.
#
# Clawd, the Claude Code mascot, lives on the right. Now and then the two throw
# a ball to each other. A big pixel clock and the date sit in the background.
# When both are idle they also do things together: a fight with a dust cloud
# that ends in a hug, a chase around the world, a dance party, sharing a snack
# and leapfrog.
#
# Every few minutes a wannabe pirate (Guybrush fan art) walks in, shouts "BUH!"
# and scares both of them off the screen. They come back once he's gone.
#
# Clawd also shows the status of the coding agents in Herdr: the herdr-plugin/
# in this repo broadcasts it over UDP on every change. Working: Clawd types on
# a laptop. Blocked (waiting for you): "!" and blinking LEDs. Done: a green tick.
#
# The hamster runs the build pipelines: herdr-plugin/pipelines.py sends their
# state. Running: the hamster runs in its wheel. Failed: the wheel stops, red
# sign, red LEDs. Green again: it cheers.
#
# Home Assistant (ha_config.py, HA_TOKEN in secrets.py): the sky behind the
# clock shows the weather and both dress for it: a beanie when it freezes or
# snows, breath clouds when it's cold, umbrellas in the rain and sunglasses
# when it's hot.
#
# Swipe left or right through the pages: scene, today, agents, pipelines,
# home, settings and apps (starts the other apps, see desk/apps.py). This file
# is only the main loop, the rest lives in desk/:
#   gfx, prefs, sound, leds   screen and palette, settings, buzzer, LEDs
#   pages, apps               the pages next to the scene; the other apps
#   data/herdr                agents, pipelines and the daily note from the PC
#   data/ha                   Home Assistant
#   scene/scene               sky, clock, wheel, characters: the main page
#   scene/sprites, actors     Messy, Clawd and the pirate, their state machines
#   scene/directors, duo      ball game and pirate visit; scenes for two
#   scene/seasons, particles  meadow, seasonal particles, holidays; all particles
#   scene/reminder, critters  the pirate before an appointment; bird and snail

import network
import time

from desk import leds, pages, sound
from desk.data import ha, herdr
from desk.gfx import WIDTH, presto, touch
from desk.prefs import settings
from desk.scene import critters, particles, reminder, scene, seasons
from desk.scene.actors import DIRECTED, FREE, Clawd, Messy
from desk.scene.directors import Ball, Visit, visit_due
from desk.scene.duo import Duo
from desk.scene.scene import WHEEL_CX
from desk.scene.sprites import BASE_Y, C_BASE_Y, CS, S

# WiFi only after Presto() (created in desk.gfx), which resets the radio.
# The first try right after boot can fail, so keep_wifi() tries again.
wlan = network.WLAN(network.STA_IF)
try:
    from secrets import WIFI_PASSWORD, WIFI_SSID
except ImportError:
    WIFI_SSID = None
WIFI_RETRY_MS = 10000
wifi_next_try = 0


def keep_wifi(now):
    """Try to (re)connect every 10 s while the link is down."""
    global wifi_next_try
    if not WIFI_SSID or wlan.isconnected() or time.ticks_diff(now, wifi_next_try) < 0:
        return
    wifi_next_try = time.ticks_add(now, WIFI_RETRY_MS)
    try:
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    except OSError:
        pass

FRAME_MS = 25  # ~30 fps on the scene, which takes longer than that to draw
CLAWD_FOR = {"working": "work", "blocked": "alert", "done": "done"}  # agent status -> Clawd
MESSY_FOR = {"running": "wheel", "failed": "broken"}  # pipeline status -> Messy
H_UMBRELLA = ("idle", "look", "walk", "sleep", "sad", "startle")  # states that hold one in the rain
C_UMBRELLA = ("idle", "look", "walk", "think", "wave", "sleep", "sad", "done")

messy = Messy()
clawd = Clawd()
hp, cp = messy.pose, clawd.pose
director = None  # Ball, Duo or Visit while one runs

view = "scene"
was_touched = False
touch_start = touch_last = None
name_tag = None  # (actor, until): name bubble after a tap
shown_pipe = None  # pipeline status the hamster last reacted to
cheer_until = 0
BROKEN_MS = 2 * 60 * 1000  # how long Messy sits in the broken wheel after a failure
last_pipe = None  # pipeline status of the last frame
failed_at = None  # when the last pipeline failed
frame = 0


def handle_touch(now):
    """A swipe switches pages, a tap (on release) pokes Messy or Clawd or
    flips a setting."""
    global was_touched, touch_start, touch_last, view, name_tag
    touch.poll()
    tapped = None
    if touch.state:
        touch_last = (touch.x, touch.y)
        if not was_touched:
            touch_start = touch_last
    elif was_touched and touch_start:
        dx = touch_last[0] - touch_start[0]
        if abs(dx) > 40:
            i = pages.VIEWS.index(view) + (1 if dx < 0 else -1)
            view = pages.VIEWS[i % len(pages.VIEWS)]
            sound.on_scene = view == "scene"
            if view != "scene":
                sound.stop_music()
        elif view == "scene":
            tapped = touch_start
        elif view == "settings":
            pages.tap_settings(*touch_start)
        elif view == "apps":
            pages.tap_apps(touch_start[0], touch_start[1], now)
    was_touched = touch.state
    if not tapped or director:
        return
    if tapped[0] < WIDTH // 2:
        name_tag = (messy, time.ticks_add(now, 1800))
        if messy.state == "sleep":
            messy.start("startle")
        elif messy.state not in ("happy", "startle"):
            messy.start("happy")
            if clawd.state in FREE:
                clawd.start("wave")
    else:
        name_tag = (clawd, time.ticks_add(now, 1800))
        if clawd.state != "happy":
            clawd.start("happy")


def next_state(actor, other, now):
    """The actor's state ran out: pick the next one, maybe with a director.
    Not while a status wants it (wheel, laptop): no game may start then. At
    night they just sleep."""
    global director
    if (messy_wanted(now) if actor is messy else clawd_wanted()):
        actor.start("idle")  # follow_pipelines / follow_agents take over right after
        return
    if seasons.bedtime(now):
        actor.start("sleep")
        return
    name = actor.pick(other.state)
    if name == "ball":
        director = Ball(messy, clawd)
    elif name == "duo":
        director = Duo(messy, clawd)
    else:
        actor.start(name)


def follow_pipelines(now):
    """Pipeline status takes over Messy, but never during a director."""
    global shown_pipe, cheer_until, last_pipe, failed_at
    status = herdr.pipe_status
    if status == "failed" and (last_pipe != "failed" or herdr.pipe_beep == "pipe_fail"):
        failed_at = now  # one more failure: back into the broken wheel for a while
    last_pipe = status
    if status != shown_pipe and messy.state not in DIRECTED:
        if shown_pipe == "running" and status == "success":
            messy.start("happy")  # all green: cheer
            cheer_until = time.ticks_add(now, 4000)
        elif shown_pipe == "running" and status == "failed":
            messy.start("startle")
        shown_pipe = status
    if herdr.pipe_beep:
        sound.play(herdr.pipe_beep)
        herdr.pipe_beep = None
    if messy.state in DIRECTED or messy.state in ("happy", "startle"):
        return
    wanted = messy_wanted(now)
    if wanted and messy.state != wanted:
        messy.x = messy.target = WHEEL_CX - 8 * S
        messy.start(wanted)
    elif not wanted and messy.state in ("wheel", "broken"):
        messy.start("idle")


def messy_wanted(now):
    """wheel, broken or None, from the pipeline status."""
    wanted = MESSY_FOR.get(herdr.pipe_status)
    if wanted == "broken" and not showing_failure(now):
        return None  # sat there long enough, the cross in the bar stays
    return wanted


def clawd_wanted():
    """work, alert, done or None, from the agent status."""
    return CLAWD_FOR.get(herdr.agent_status)


def showing_failure(now):
    """A pipeline failed within BROKEN_MS: broken wheel and red LEDs."""
    return (herdr.pipe_status == "failed" and failed_at is not None
            and time.ticks_diff(now, failed_at) < BROKEN_MS)


def follow_agents(now):
    """Agent status takes over Clawd. A question for you even ends a game."""
    global director
    if herdr.agent_beep:
        sound.play("agent_alert" if herdr.agent_beep == "alert" else "agent_done")
        if herdr.agent_beep == "done":
            clawd.flash_until = time.ticks_add(now, 2500)
        herdr.agent_beep = None
    wanted = clawd_wanted()
    if wanted == "alert" and director and director.interruptible:
        director = None
        messy.start("idle")
        clawd.start("idle")
    if clawd.state in DIRECTED or clawd.state == "happy":
        return
    if wanted and clawd.state != wanted:
        clawd.start(wanted)
    elif not wanted and clawd.state in ("work", "alert", "done"):
        clawd.start("idle")


def pose(now, k):
    """Move everyone and work out how they look in this frame. Returns what
    they wear."""
    global director
    hp.reset()
    cp.reset()
    messy.act(now, k, hp)
    clawd.act(now, k, cp)
    if director and not director.update(now, k, hp, cp):
        director = None
    critters.react(messy, hp)
    messy.finish(now, hp)
    clawd.finish(now, cp)

    if time.ticks_diff(cheer_until, now) > 0:
        hp.bubble = "tick"
    if name_tag and time.ticks_diff(name_tag[1], now) > 0 and name_tag[0].pose.bubble is None:
        name_tag[0].pose.bubble = "name"

    # dress for the weather
    wear, rain, breath = ha.outfit()
    if rain and messy.state in H_UMBRELLA:
        hp.umbrella = True
        hp.paws = ((13, 7),)
    if rain and clawd.state in C_UMBRELLA:
        cp.umbrella = True
        cp.arms = (True, cp.arms[1] if clawd.state == "wave" else False)
    if breath and view == "scene":
        if frame % 75 == 0 and messy.state not in ("event", "duo"):
            particles.spawn("breath", messy.x + 9 * S, BASE_Y + 7 * S - hp.jump, 0.8, -0.3, 18)
        if frame % 75 == 37 and clawd.state not in ("event", "duo", "work"):
            particles.spawn("breath", clawd.x + 15 * CS, C_BASE_Y + 3 * CS - cp.jump, 0.7, -0.3, 18)
    return wear


def update_leds(now):
    """Status signals (LEDS switch) beat the animation lights (ANIM LIGHTS)."""
    status, own = None, ()
    if settings["leds"]:
        own = leds.agent_colours(now)  # one LED per agent
        if showing_failure(now):
            status = "failed"
    mood = director.mood(now) if director else None
    if not settings["anim_leds"]:
        leds.update(status, now, own)
    elif mood:
        leds.update(mood[0], mood[1], own)
    elif status:
        leds.update(status, now, own)
    else:
        leds.update(messy.state, messy.elapsed(now), own)


last_now = time.ticks_ms()
while True:
    now = time.ticks_ms()
    k = min(3.0, time.ticks_diff(now, last_now) / 66)  # frame time in units of 66 ms
    last_now = now

    handle_touch(now)
    if (not director and messy.state not in ("wheel", "broken") and clawd.state not in ("work", "alert")
            and visit_due(now) and not seasons.bedtime(now)):  # only when neither is busy working
        director = Visit(messy, clawd, now)
    if messy.timed_out(now):
        next_state(messy, clawd, now)
    if clawd.timed_out(now):
        next_state(clawd, messy, now)

    herdr.poll(now)  # every frame: the radio only buffers a few packets
    if frame % 4 == 0:
        keep_wifi(now)
        scene.sync_clock(now)
    ha.poll(now)
    follow_pipelines(now)
    follow_agents(now)

    wear = pose(now, k)
    critters.update(now, k, messy, clawd, cp, seasons.bedtime(now))
    reminder.update(now, k, isinstance(director, Visit))  # not while he's really here
    particles.update(k)

    if view == "scene":
        seasons.spawn(now, k)
        scene.draw(now, messy, hp, clawd, cp, director, wear)
        pages.draw_page_dots("scene")
        pages.forget()
        redraw = True
    else:
        redraw = pages.show(view, now)

    update_leds(now)
    if redraw:
        presto.update()
    frame += 1
    time.sleep_ms(max(0, FRAME_MS - time.ticks_diff(time.ticks_ms(), now)))
