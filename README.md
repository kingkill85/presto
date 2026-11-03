# presto

My own apps for the [Pimoroni Presto](https://shop.pimoroni.com/products/presto)
(RP2350, 4" touch screen, MicroPython).

Runs on Presto firmware **v1.0.0**. v2.0.0 hangs on every flash write
([pimoroni/presto#121](https://github.com/pimoroni/presto/issues/121)).

## Files

Everything in `device/` goes to the root of the Presto's filesystem.

| File | What it does |
| --- | --- |
| `main.py` | Boots into the start screen (`desk.main`), or once into the app picked on its apps page. |
| `desk/` | The start screen: Messy, a pixel hamster desk pet, and Clawd (the Claude Code mascot) plus the status pages. `main.py` is the loop, `scene/` the meadow and characters, `data/` Herdr and Home Assistant. See below. |
| `games.py` | Unified game library with virtual system folders; starts only the selected native engine. |
| `gb.py` | Internal Retro runtime for GB, GBC, Game Gear, NES and Master System. |
| `scumm.py` | Internal experimental SCUMM-v4/v5 runtime for German Monkey Island VGA and Monkey Island 2, with touch/gamepad input and switchable zoom. |
| `lib/` | Shared helpers (on `sys.path`): `haclient.py`, a non-blocking Home Assistant REST client (one small step per frame), and `tz.py`, German local time (CET/CEST) from the UTC set by `ntptime`. |
| `ha_config.example.py` | Template for `ha_config.py`: Home Assistant host and which entities to show. |
| `sdcard.py` | SD card driver from micropython-lib ([PR #765](https://github.com/micropython/micropython-lib/pull/765), MIT). Stays in the root: `.frozen` comes before `/lib` in `sys.path`, so only here does it replace the built-in one, which fails with "timeout waiting for v2 card" ([pimoroni/presto#79](https://github.com/pimoroni/presto/issues/79)). |
| `secrets.example.py` | Template for `secrets.py` (WiFi and Home Assistant token). |

The app page has one **Spiele** entry for Retro and SCUMM. Bundled Pimoroni demo apps
and their example images/fonts have been removed; the launcher still discovers
additional root-level Python apps automatically.

## Messy and Clawd

A 240×240 pixel scene in the PICO-8 palette, running at about 30 fps.

- **Messy** (the hamster) idles, sniffs, looks around, walks, eats seeds,
  washes, digs for seeds, sneezes, sleeps and stretches when he wakes up.
  **Clawd** waves, thinks, walks, drinks coffee and juggles. Tap either one:
  it cheers (or wakes up) and shows its name.
- **Together** they play catch and act out little scenes: a fight in a dust
  cloud that ends in a hug, a chase around the world, a dance party, sharing a
  snack, leapfrog, hide and seek, and one for the season (a snowman, kicking
  leaves, watering a flower, ice cream).
- **Little mischief:** Clawd folds a paper plane that loops back onto Messy's
  head, conjures an oversized seed from a magician's hat, and plays a mirror
  game with Messy that ends in two very theatrical sneezes.
- **Visitors:** a bird that sometimes lands on Clawd's head, and now and then
  a snail crawling across the meadow.
- **Guybrush** (Monkey Island 2 style fan art) comes by now and then (every 30 to 60
  minutes, so it stays special) while neither of them is working. His eight-frame
  walk cycle includes swinging arms, coat and ponytail. He introduces himself as a mighty
  pirate (Clawd sometimes gets his name wrong) and then, with little nods to the games:
  shouts "BUH!" and scares both off; brings a treasure map, Messy digs up the chest and the
  treasure is... a T-shirt; points at a three-headed monkey and steals Clawd's coffee; fights Clawd
  (sabre against fork) with insults; or holds a spitting contest that Messy wins with a seed from his
  cheeks. He brings a jingle, or your own melody
  from `guybrush.rtttl` (RTTTL ringtone format, git-ignored) on the Presto.
- **Background:** a big pixel clock with weekday and date (NTP), the next
  appointment of the day below it, the weather symbol top left, temperature
  and weather top right, a sky colour that follows
  the daylight and a meadow that changes with the seasons: tulips and
  petals in spring, poppies, a butterfly and fireflies in summer, mushrooms
  and falling leaves in autumn, snow and a frozen puddle in winter. Eggs at
  Easter, a pumpkin at Halloween, a little tree from Advent to Epiphany and
  fireworks on New Year's Eve.
- **Mood LEDs** on the back follow what's going on.

- **Daily note:** appointments and tasks from today's note in Obsidian (sent by
  the pipeline poller, see `herdr-plugin/daynote.py`). 10 and 2 minutes before
  an appointment Guybrush walks in, turns to you and reminds you.

Swipe left or right through seven pages:

1. the scene
2. **HEUTE**: today's appointments and tasks from the daily note
3. **AGENTS**: the coding agents in Herdr and their status, the ones waiting for you and working
   first; with many agents the idle ones share one line and the rows get smaller. Below them
   Claude's usage limits (5 hours and week, see below)
4. **PIPELINES**: CI pipelines of the active Herdr spaces; when they don't fit, the passed ones share one line and the rows get smaller
5. **HOME**: Home Assistant weather, rooms, lights, heating, low batteries
6. **SETTINGS**: switch status LEDs, animation lights, sounds, animation sounds and music on or off (saved in
   `settings.json` on the Presto)
7. **APPS**: every other `*.py` in the root as a tile (except config and `sdcard.py`, see `HIDDEN` in
   `desk/apps.py`, 12 at most). A tap resets the Presto into that app; the next reset brings the start screen back.

## Qw/ST Pad

The optional Pimoroni Qw/ST Pad works alongside touch on the desk. Plug it into the
Presto's Qw/ST port; it is detected automatically, including after reconnecting.
The desk also works without a controller. The Retro console requires the pad;
unplugging it saves and pauses the game until the controller is reconnected.

On the desk, **+ / −** move to the next / previous page. **Left / right**
also switch pages except on APPS, where the D-pad selects a tile. On SETTINGS,
**up / down** select a row. **A** opens the selected app or toggles the selected
setting. **Y** opens APPS; **X** returns to the scene, as does **B** from another
page. On the scene, **A / B** greet Messy / Clawd. A border marks the selected
app or setting while a controller is connected.

The **Spiele** app groups installed games into virtual GB, GBC, Game Gear, NES,
Master System and Adventures folders. Empty folders are hidden. Selection works
with touch or the pad; Retro gameplay still requires the pad. Files stay in place.
The ROM scanner provides one list for `.gb`, `.gbc`, `.gg`, `.nes`
and `.sms`. It discovers games recursively in `/roms` and `/sd/roms`, including
system subfolders. The native core is imported only after choosing a game.
A `.gb` cartridge with a CGB hardware flag also selects the color core.

GB, GBC and Game Gear use exact **3× integer scaling**: 480×432 centered on
480×480 with 24 black pixels above and below. NES and Master System default to **2× integer scaling**: 480×480 for NES
and usually 480×384 for SMS. Eight original pixels are cropped from each side.
Use **Vergroesserung** in the shared menu to switch to the complete centered
1× image and back, including GB/GBC/Game Gear.
No overlays or stretching.
The renderer writes directly to the display buffer (`direct_to_fb=True`).
NES and SMS cap rendering at **30 FPS** while emulating at the original console
rate (about 60 frames per second). When drawing is too expensive, additional
images are skipped so the game can keep its speed; 30 displayed FPS are not
guaranteed for every game. Other systems keep adaptive rendering.

During emulation the CPU runs at **300 MHz**. The original clock (200 MHz on
our device) is restored for save writes, a disconnected controller, errors and
exit. ROM loading and menus retain the original clock. Unsupported clock
requests fall back to the original frequency. No voltage-register changes or
firmware replacement are made by the app.

Short gameplay comparisons on this Presto measured these average rendered-frame
core times; all samples maintained about 60 emulated / 30 displayed FPS:

| CPU clock | NES Mario 3, level 1-1 | SMS Sonic |
| --- | ---: | ---: |
| 200 MHz | 20.2 ms | 18.0 ms |
| 240 MHz | 16.9 ms | 15.0 ms |
| 264 MHz | 15.3 ms | 13.6 ms |
| 300 MHz | 14.7 ms | 13.2 ms |

These are short tests on one board, not a stability guarantee for every Presto.
`tests/check_retro_clock_device.py` compares fixture framebuffer checksums at
200/300 MHz and checks a megabyte of PSRAM. `CPU_MHZ` in the gameplay benchmark
selects a comparison clock. The emulator keeps its original pacing at every
clock; extra speed provides headroom rather than speeding up gameplay.
The reproducible gameplay benchmark in
`tests/benchmark_retro_device.py` measures CPU-only and rendered frames separately.
It loads the core after ROM allocation, matching the app's startup order.
A visually verified 120-frame stationary sample in Mario 3 level 1-1 measured
about 60 emulated / 30 displayed FPS with the decoded CHR-ROM cache, up from
about 15 displayed FPS without it. The 32-entry cache uses an extra 128 KiB and
avoids repeated decoding/copying during MMC3 bank switches. Earlier world-map figures are not level
performance measurements. Longer unattended tests can die and return to the map. SMS Sonic reached about 60 / 30
in both the short test and a 2400-frame (40-second) gameplay test.
These are specific gameplay samples, not guarantees for every ROM or scene.


The D-pad and **A / B** control the game; **−** is SELECT on GB/GBC/NES and
**+** is START (Pause on Master System). **SELECT + START** opens the same game
menu for every system: resume, save, load, enlargement on/off, restart and return
to the game library. The chord is consumed before reaching the game; short single
Start/Select presses are preserved. X+Y no longer exits; Y/Select no longer zoom.
Menus match the desk's pixel type, sky palette, garland and flat outlined tiles.

There are **five state slots per game**, with a timestamp or "Leer" and confirmation
before overwriting. GB/GBC/GG/SMS/NES support complete states. SCUMM uses its native
save format and disables saving/loading when game scripts forbid it. Retro states
live in `/sd/saves/<game-path-hash>/`; checksum, ROM SHA256, core version and size
are checked before loading. Temporary files and a recovery backup protect an
existing slot during replacement. Native state formats may change with core
updates; battery saves remain separate. Hardware checks cover deterministic
restore and reinitialization for GB/GBC/GG/SMS/NES, all six supported NES
mappers, five GB and NES slots across a reset, and SCUMM save/load for both
Monkey Island profiles. NES checks also cover installed games, rejected corrupt
states and the shared pause/zoom/exit flow. Menu enlargement is stored per game in
`/sd/games.json`. Engine switches/restarts use a clean device reset.

Battery RAM is saved next to the ROM as `.sav`; disconnecting saves and pauses,
and reconnecting resumes. All cores currently run **without audio**. NES uses
InfoNES and supports mappers 0, 1, 2, 3, 4 and 7. It accepts iNES 1 and ordinary
NTSC NES 2.0 dumps; extended sizes, submappers and unsupported RAM/CHR layouts
are rejected. The GB core is Peanut-GB, GBC uses Walnut-CGB, and GG/SMS share
TotalSMS. Exact upstream revisions and port changes are in each native core's
`UPSTREAM.txt`, with licenses under `vendor/`.

The driver is `device/lib/gamepad.py`, using the
[official Qw/ST Pad register mapping](https://github.com/pimoroni/qwstpad-micropython).
It supports addresses 0x21, 0x23, 0x25 and 0x27 on the external I2C bus
(SDA GPIO40, SCL GPIO41). Missing controllers are retried once per second.

## Experimental SCUMM games

**SCUMM** runs **The Secret of Monkey Island (German DOS VGA)** and
**Monkey Island 2 (German DOS)** through native SCUMM-v4/v5 engines derived
from FRANK Quest/Cabal. Choose the game with the D-pad and A, or tap its row.
It works on the existing Presto firmware, tested at the normal **200 MHz**.
These are two explicit game profiles, not the general ScummVM launcher.
Audio remains disabled. Five native SCUMM save slots are available through the shared menu.

The complete 320×200 image defaults to **480×300 nearest-neighbour zoom**,
centered with black bars. This optional 1.5× mode has uneven pixel sizes but
no smoothing or cropping. The shared menu switches to exact 1× and back.
The D-pad moves the mouse, **A / B** click left/right, **X** skips a cutscene,
**Y** pauses and **START / +** sends Enter. **SELECT + START** opens the menu.
Touch works without a pad: tap the game to click or the unused upper black
border to open the same menu.

Monkey Island's `.LFL` and `.LEC` files belong in `/sd/scumm/monkey-vga-de`.
Monkey Island 2 uses `monkey2.000` and `monkey2.001` in `/sd/scumm/monkey2-de`.
Only complete installations appear in the selection. Index checksums reject
other editions instead of guessing the engine/language. Game data are not
included in git. Build and deployment instructions are in
[`native/scumm/README.md`](native/scumm/README.md).

## Optional Multi-Sensor Stick

The desk uses the stick's LTR559 light/proximity sensor when connected. Screen
backlight and LED intensity fade with room light; the existing sun-based sky,
clock colours and nighttime routine remain in charge of the scene.
Without the stick, normal brightness returns smoothly and touch/gamepad control
continue working. Missing sensors are retried every two seconds.

Hold a hand close to the sensor for about a second to invite Guybrush with his
lantern. Messy and Clawd do not perform a separate sensor greeting or search. He lights both characters while
their work status continues unchanged. Holding the sensor covered only triggers
one visit; release it before inviting him again. Lantern visits can accompany sleep and other scenes, but only appear on the
scene page. Missing sensors cannot start visits.

When room light stays below 3 lux for two seconds, Guybrush brings a lantern
and lights both characters, who keep their current work status. He leaves again
after a short visit. The trigger rearms above 8 lux, with at least five minutes
between visits; hand-triggered visits are independent of this automatic darkness cooldown. A first reading at boot or after reconnect establishes the starting light level
without inviting him. Visits wait for the scene page and cancel on sensor loss.

The Home Assistant page shows a compact room-climate tile (temperature in Celsius,
relative humidity and local pressure in hPa), even while Home Assistant is unavailable. Room rows compact automatically to
leave space for the sensor values and battery warnings.
The optional BME280 takes a measurement every five seconds; start and read happen
on separate frames. Missing sensors hide the tile and retry every two seconds.
On the main scene, outdoor (sun) and indoor (house) temperatures alternate every
30 seconds while the local sensor supplies a valid value. Without it, only
the outdoor value appears; without outdoor data, the indoor value stays visible.
Pressure is measured at the device, not corrected to sea level; nearby electronics
can warm the temperature sensor.

The optional LSM6DS3TR-C motion sensor calibrates its resting orientation after
about one second held still. Tilting the stick makes idle characters balance,
a single tap makes them look forward, and shaking makes them briefly stumble.
Tap/shake reactions have a two-second cooldown. These pose overlays can appear
during every activity without changing work status or interrupting directors.
Shaking causes three seconds of stumbling, taps cause 3.5 seconds of looking
around, and tilting adds alternating balance steps. Sleeping characters wake
for six seconds and look around before resuming sleep; holding a
tilt does not keep them awake. Only sensor motion/lantern reactions bypass the
sleep/activity restrictions. Off-page gestures are discarded. A loose stick senses its own movement; mount it on the Presto to
react to movement of the whole device. Disconnects/stale data clear the effect,
retry every two seconds and recalibrate after reconnecting.

Motion register reference: [Pimoroni LSM6DS3 driver](https://github.com/pimoroni/lsm6ds3-micropython).
The local driver uses bounded I2C reads and non-blocking calibration; hardware
polling and synthetic gesture rendering are checked on the device. Physical
tap/shake sensitivity may need tuning for the stick's mounting.

## Home Assistant

`device/lib/haclient.py` fetches entity states from Home Assistant over plain HTTP
on the local network with non-blocking sockets, so the animation never stalls.
`device/ha_config.py` lists what to show (copy it from `ha_config.example.py`,
it stays out of git); the token goes into `secrets.py` as `HA_TOKEN`.

The sky follows the weather (stars at night, rain, snow, fog, lightning), Messy
and Clawd dress for it (beanie when freezing or snowing, breath clouds when
cold, umbrellas in the rain, sunglasses above 26 °C), and the HOME page shows
weather, rooms (lights, temperatures, heating) and batteries below
`LOW_BATTERY` percent.

## Herdr plugin

`herdr-plugin/` shows the status of your coding agents in [Herdr](https://herdr.dev)
on the Presto. On every agent status change it broadcasts the combined status
(blocked > working > done > idle) as UDP to port 47474. Clawd then types on a
laptop (working), waves with a "!" and three beeps sound (blocked, waiting for
you), or shows a green tick with a ding-dong (done). With several agents, a
bar on the right of the scene shows each one, Clawd briefly holds up a tick
when one finishes while others still work, and the first LEDs on the back
get one agent each (steady blue = working, green = done, blinking orange =
waiting for you).

```sh
herdr plugin link "$PWD/herdr-plugin"
```

The Presto needs WiFi (`secrets.py`) on the same network. If broadcast doesn't
reach it, write its IP into `$(herdr plugin config-dir presto.clawd)/target`.

## CI pipelines of the active spaces

The same plugin also runs `herdr-plugin/pipelines.py`. Every 30 s it asks
Herdr for its workspaces (spaces) and the directories of their panes and finds
the git repos and checked out branches there. For each repo it shows the CI of
the checked out branch plus the CI of my open MRs/PRs in that repo (updated in
the last 7 days), so nothing has to be checked out to be seen: on GitLab (via
`glab api`) an MR's head pipeline or the newest branch pipeline, on GitHub (via
`gh api`) the newest Actions run. Pinned refs from the config (e.g. a team's
develop branch) are added. Rows without CI are left out; running pipelines
come first, then failed ones, then the most recent. It also repeats the agent
status, so the Presto catches up after a restart.

While pipelines run, Messy jogs in the wheel now and then and the rim fills
up in blue with the jobs done of all of them together (a sign on top shows how
many run). A failed pipeline stops the wheel, smokes and
pulses the LEDs red; when it turns green Messy cheers. Different beeps sound
when a pipeline starts, passes or fails.

Herdr starts the poller with the server and `poller_ctl.py ensure` restarts it
on workspace focus if needed. When Herdr goes away the poller tells the Presto
that nothing is going on any more and exits; if the PC just disappears, the
Presto drops agents and pipelines after 3 minutes without updates. Control it with
the plugin actions `presto.clawd.pipelines-start|stop|restart|status`.
Settings go into `$(herdr plugin config-dir presto.clawd)/pipelines.json`:

```json
{"interval": 30, "pinned": [{"host": "gitlab.example.com", "project": "group/project", "ref": "develop"}]}
```

Without `"pinned"` only the spaces are shown. Needs `glab`/`gh` logged in.

## Claude usage limits

The poller also sends Claude's usage limits (the 5 hour window and the week,
with the time each resets) from `herdr-plugin/usage.py`; the AGENTS page shows
them as two bars (green, yellow from 50 %, red from 80 %). Claude Code only
hands them to its status line script, so that script has to save them. Add
this to yours (needs `jq`; `$input` is the JSON Claude Code passes in):

```sh
printf '%s' "$input" | jq -c 'select(.rate_limits) | .rate_limits + {ts: now}' \
  > ~/.cache/presto-usage.json.tmp && mv ~/.cache/presto-usage.json.tmp ~/.cache/presto-usage.json
```

The file is only as fresh as the last Claude session; a window that has reset
since then counts as 0 %. With several computers the newest data wins.

## Deploy

```sh
cp device/secrets.example.py device/secrets.py      # fill in, never commit
cp device/ha_config.example.py device/ha_config.py  # optional: Home Assistant
mpremote fs cp device/*.py :
mpremote fs cp -r device/desk device/lib :
mpremote fs cp guybrush.rtttl :                     # optional: your own melody
mpremote reset
```

The Retro console also needs its native modules, built against MicroPython
**v1.26.0** with the ARM embedded GCC toolchain and Python `pyelftools` installed:

```sh
make -C native/gb MPY_DIR=/path/to/micropython
make -C native/gbc MPY_DIR=/path/to/micropython
make -C native/sms MPY_DIR=/path/to/micropython
make -C native/nes MPY_DIR=/path/to/micropython
mpremote fs cp native/gb/gbcore.mpy native/gbc/gbccore.mpy native/sms/smscore.mpy native/nes/nescore.mpy :lib/
```

On NixOS, add `MKDIR=mkdir RM=rm` to the make commands. Generated `.mpy` files
are not committed. Host checks: `python3 -m unittest discover -s tests -v`.
The original CPU/video test programs can also be checked directly on a board:

```sh
mpremote mount tests + exec "KIND='NES'; SCALE=2" + run tests/check_retro_device.py
```

Use `GBC`, `GG`, `SMS` or `NES` as `KIND`; `SCALE=1/2` selects the NES/SMS
presentation mode. These checks use no downloaded game data.
