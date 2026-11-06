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

from climate_sensor import ClimateSensor
from darkness import Darkness
from motion_sensor import MotionSensor
from ambient_sensor import AmbientSensor
from gamepad import A, B, DOWN, LEFT, RIGHT, SELECT, START, UP, X, Y, Gamepad

from desk import leds, pages, sound
from desk.data import ha, herdr
from desk.gfx import WIDTH, presto, touch
from desk.prefs import settings
from desk.scene import critters, particles, reminder, scene, seasons
from desk.scene.actors import DIRECTED, FREE, Clawd, Messy
from desk.scene.directors import Ball
from desk.scene.pirate import Visit, visit_due
from desk.scene.duo import Duo
from desk.scene.lantern import Lantern
from desk.scene.motion import MotionReaction
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
DONE_MS = 2 * 60 * 1000  # how long Clawd holds up the tick: a finished agent nobody looked at stays "done"
done_at = None  # when the combined agent status turned "done"
frame = 0
pad = Gamepad()
ambient = AmbientSensor()
climate = ClimateSensor()
motion = MotionSensor()
motion_reaction = MotionReaction(particles.spawn)
pages.climate = climate
scene.climate = climate
darkness = Darkness()
lantern = None
backlight_shown = 1.0
ambient_search_seen = False
pad_setting = pad_app = 0


def change_view(name):
    global view
    view = name
    sound.on_scene = view == "scene"
    if view != "scene":
        sound.stop_music()


def handle_gamepad(now):
    global pad_setting, pad_app
    pad.poll(now)
    actions, pressed = pad.actions, pad.pressed
    if pressed & X or (pressed & B and view != "scene"):
        change_view("scene")
    elif pressed & Y:
        change_view("apps")
    elif pressed & (START | SELECT):
        i = pages.VIEWS.index(view) + (1 if pressed & START else -1)
        change_view(pages.VIEWS[i % len(pages.VIEWS)])
    elif view == "apps":
        from desk import apps

        found = apps.get()
        if found:
            if actions & LEFT:
                pad_app = max(0, pad_app - 1)
            elif actions & RIGHT:
                pad_app = min(len(found) - 1, pad_app + 1)
            elif actions & UP:
                pad_app = max(0, pad_app - pages.APP_COLS)
            elif actions & DOWN:
                pad_app = min(len(found) - 1, pad_app + pages.APP_COLS)
            if pressed & A:
                x, y = pages.app_slot(pad_app)
                pages.tap_apps(x + 1, y + 1, now)
    else:
        if actions & (LEFT | RIGHT):
            i = pages.VIEWS.index(view) + (1 if actions & RIGHT else -1)
            change_view(pages.VIEWS[i % len(pages.VIEWS)])
        elif view == "settings":
            if actions & UP:
                pad_setting = (pad_setting - 1) % len(pages.SETTING_ROWS)
            elif actions & DOWN:
                pad_setting = (pad_setting + 1) % len(pages.SETTING_ROWS)
            if pressed & A:
                pages.tap_settings(16, pages.SETTING_Y0 + pad_setting * pages.SETTING_H)
        elif view == "scene":
            if pressed & A:
                poke((0, 0), now)
            elif pressed & B:
                poke((WIDTH - 1, 0), now)
    if pad.connected and view in ("apps", "settings"):
        pages.pad_focus = (view, pad_app if view == "apps" else pad_setting)
    else:
        pages.pad_focus = None


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
            change_view(pages.VIEWS[i % len(pages.VIEWS)])
        elif view == "scene":
            tapped = touch_start
        elif view == "settings":
            pages.tap_settings(*touch_start)
        elif view == "apps":
            pages.tap_apps(touch_start[0], touch_start[1], now)
    was_touched = touch.state
    poke(tapped, now)


def poke(tapped, now):
    global name_tag, director
    if not tapped:
        return
    if director:
        if not director.interruptible:  # Guybrush is visiting: just the name
            name_tag = (messy if tapped[0] < WIDTH // 2 else clawd, time.ticks_add(now, 1800))
            return
        director = None  # a tap ends a game or a scene: they react to you instead
        sound.stop_music()
        messy.start("idle")
        clawd.start("idle")
    if tapped[0] < WIDTH // 2:
        name_tag = (messy, time.ticks_add(now, 1800))
        if messy.state == "sleep":
            wake_up(now)
            messy.start("startle")
        elif messy.state not in ("happy", "startle"):
            messy.start("happy")
            if clawd.state in FREE:
                clawd.start("wave")
    else:
        name_tag = (clawd, time.ticks_add(now, 1800))
        if clawd.state == "sleep":
            wake_up(now)
        if clawd.state != "happy":
            clawd.start("happy")


AWAKE_MS = 3 * 60 * 1000  # woken up by you (sensor, tap): stay up this long
awake_until = None


def kept_awake(now):
    return awake_until is not None and time.ticks_diff(awake_until, now) > 0


def wake_up(now):
    """Someone woke them: up they get, and they stay awake for AWAKE_MS."""
    global awake_until
    awake_until = time.ticks_add(now, AWAKE_MS)
    for actor in (messy, clawd):
        if actor.state == "sleep":
            actor.start("idle")


def next_state(actor, other, now):
    """The actor's state ran out: pick the next one, maybe with a director.
    Not while a status wants it (wheel, laptop): no game may start then. At
    night they just sleep."""
    global director
    if (messy_wanted(now) if actor is messy else clawd_wanted(now)):
        actor.start("idle")  # follow_pipelines / follow_agents take over right after
        return
    night = seasons.bedtime(now)
    if night and not kept_awake(now):
        actor.start("sleep")
        return
    name = actor.pick(other.state)
    if (lantern or night) and name in ("ball", "duo"):
        name = "look"  # no games at night, even when someone woke them
    if name == "sleep" and kept_awake(now):
        name = "look"
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


def clawd_wanted(now):
    """work, alert, done or None, from the agent status. "done" only for
    DONE_MS: it stays until you look at the agent in Herdr, maybe for hours."""
    global done_at
    wanted = CLAWD_FOR.get(herdr.agent_status)
    if wanted != "done":
        done_at = None
        return wanted
    if done_at is None:
        done_at = now
    return wanted if time.ticks_diff(now, done_at) < DONE_MS else None


def showing_failure(now):
    """A pipeline failed within BROKEN_MS: broken wheel and red LEDs."""
    return (herdr.pipe_status == "failed" and failed_at is not None
            and time.ticks_diff(now, failed_at) < BROKEN_MS)


def follow_agents(now):
    """Agent status takes over Clawd. A question for you even ends a game."""
    global director, done_at
    if herdr.agent_beep:
        sound.play("agent_alert" if herdr.agent_beep == "alert" else "agent_done")
        if herdr.agent_beep == "done":
            clawd.flash_until = time.ticks_add(now, 2500)
            done_at = None  # one more finished: the tick again for DONE_MS
        herdr.agent_beep = None
    wanted = clawd_wanted(now)
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
    waking = motion_allowed(now) and motion_reaction.waking(now)
    messy.act(now, k, hp, awake=waking)
    clawd.act(now, k, cp, awake=waking)
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
    # Apply last so directors, blinking and weather cannot hide the reaction.
    if motion_allowed(now):
        motion_reaction.apply(now, motion.tilt, hp, cp,
                              (messy.state == 'sleep', clawd.state == 'sleep'),
                              ((messy.x + 8 * S, BASE_Y), (clawd.x + 8 * CS, C_BASE_Y)))
    return wear


def motion_allowed(now):
    return motion.ready and view == 'scene'


def handle_ambient(now, dt):
    global lantern, backlight_shown, ambient_search_seen
    ambient.poll(now)
    level = ambient.brightness(dt)
    if abs(level - backlight_shown) >= 0.01:
        presto.set_backlight(level)
        backlight_shown = level
    leds.ambient_scale = 0.25 + 0.75 * level
    if not ambient.covered:
        ambient_search_seen = False
    # Sensor visits may accompany sleep, work and shared animations.
    if not ambient.connected or view != 'scene':
        return
    if lantern:
        # A hand over the sensor during a visit must not queue another visit.
        if ambient.covered:
            ambient_search_seen = True
        return
    if ambient.covered and not ambient_search_seen:
        ambient_search_seen = True
        lantern = Lantern(now, messy, clawd)


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
    handle_gamepad(now)
    if (not director and not lantern and messy.state not in ("wheel", "broken") and clawd.state not in ("work", "alert")
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

    climate.poll(now)
    motion_event = motion.poll(now)
    handle_ambient(now, min(100, int(k * 66)))
    if lantern and (view != "scene" or not ambient.connected
                    or ambient.lux is None or ambient.light_at is None
                    or time.ticks_diff(now, ambient.light_at) > 3000):
        lantern = None
    if darkness.poll(now, ambient, view == "scene" and not lantern):
        lantern = Lantern(now, messy, clawd)
    if lantern and not lantern.update(now, k):
        lantern = None
    woke = motion_reaction.wake_started
    motion_reaction.update(now, motion_event, motion_allowed(now), motion.tilt)
    if motion_reaction.wake_started is not None and motion_reaction.wake_started != woke:
        wake_up(now)  # knocked, shaken or tipped: really awake now
    wear = pose(now, k)
    critters.update(now, k, messy, clawd, cp, seasons.bedtime(now))
    reminder.update(now, k, (isinstance(director, Visit) or lantern is not None))  # not while he's really here
    particles.update(k)

    if view == "scene":
        seasons.spawn(now, k)
        scene.draw(now, messy, hp, clawd, cp, director, wear, lantern)
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
