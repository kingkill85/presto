# AGENTS.md

Instructions for coding agents working anywhere in this repository.

## Project and layout

MicroPython apps for the Pimoroni Presto (RP2350, physical 480×480 touch
screen; the desk scene uses a 240×240 framebuffer). See `README.md` for
features and setup, and `CLAUDE.md` for further architectural context.

- `device/` mirrors the root of the device filesystem.
- `device/main.py` boots `desk.main`, or launches an app once using
  `/ramfs/launch.txt`. It removes the launch file before importing the app;
  the following reset returns to the desk.
- `device/desk/` is the entire start screen and launcher, not just Messy.
  `main.py` owns the loop; `gfx`, `prefs`, `sound`, and `leds` provide shared
  UI services; `pages` and `apps` implement the other pages.
- `device/desk/data/` receives Herdr status and Home Assistant data.
- `device/desk/scene/` contains the scene, character sprites, actors, scene
  directors, seasons, particles, critters, and appointment reminders.
- `device/lib/` holds shared helpers, including `haclient.py` (non-blocking
  Home Assistant client) and `tz.py` (German CET/CEST conversion from UTC).
  This directory is on the device's `sys.path`.
- `device/lib/ambient_sensor.py` polls the optional LTR559 at 0x23 without
  sleeping. Bound I2C operations, rate-limit reconnects and use wrapping ticks.
  Missing/stale sensors restore the normal backlight gradually; preserve the
  existing sun-based scene colours and bedtime. Proximity reactions must not
  interrupt external status or other directors. Covering the sensor invites
  Guybrush with `scene/lantern.py`; the actors never carry sensor-triggered lights.
  Distinguish LTR559 identity from a Qw/ST Pad at the shared alternate 0x23 address.
- `device/lib/motion_sensor.py` polls the optional LSM6DS3TR-C at 0x6a/0x6b,
  verifies identity, calibrates a stable initial orientation and retries absent
  devices without blocking. Stale/disconnected data clears reactions. The pose
  overlay in `desk/scene/motion.py` never changes actor states. Motion and lantern
  reactions may accompany every activity, including sleep, work and directors.
  Sleepers briefly wake visually, then resume sleeping even if tilt is held.
  Preserve all non-sensor activity/night gates; discard gestures off the scene page.
- `device/lib/climate_sensor.py` reads the optional BME280 at 0x76 with forced
  measurements split across frames. Clear missing/invalid values, retry with
  backoff, and include the rounded values in the Home Assistant page's redraw key.
  Reserve the climate tile and battery warning heights when laying out rooms.
- `device/lib/darkness.py` debounces room-darkness transitions separately from
  proximity (3/8 lux hysteresis, five-minute cooldown). `scene/lantern.py` draws
  Guybrush behind both actors without owning their status. Avoid repeated sensor visits; sensor-triggered lantern visits are allowed during
  sleep and other animations. Keep other bedtime/activity gates and cancel
  the lantern on sensor loss.
- `device/lib/gamepad.py` reads the optional Qw/ST Pad on external I2C
  (GPIO40/41). Desk navigation and Game Boy share it. Keep the desk usable by
  touch without a pad. Game Boy requires a pad, saves and pauses on disconnect,
  and resumes on reconnect. Rate-limit absent-device retries.
- Keep only apps and configuration in the device root, plus `sdcard.py`.
  The apps page discovers root `*.py` files except its `HIDDEN` entries;
  putting a helper there creates an unwanted launcher entry.
- `device/sdcard.py` must stay in the root: the frozen, broken built-in
  driver takes precedence over `/lib`. Our driver mounts cards at `/sd`.
- `herdr-plugin/` contains host-side Python scripts and the Herdr manifest.
- `device/games.py` is the only visible game app. `game_catalog.py` discovers
  virtual system folders without loading cores. `game_ui.py` provides the shared
  touch/pad menu; `game_launch.py` routes internal runtimes via RAMFS/reset.
  Five checked state slots are provided by `game_storage.py`; never substitute
  battery RAM for full states. NES states include CPU/PPU, mapper registers,
  pending interrupts, RAM and active decoded CHR banks. Serialize bank offsets,
  never native pointers; validate before mutation and invalidate unused caches
  on restore. Bump the state version/core ID when changing its layout.
- `device/gb.py` is the internal thin entry point for the shared Retro console in
  `device/lib/retro.py`; `retro_roms.py` discovers and selects GB/GBC/GG/NES/SMS.
  ROMs are under `/roms` or `/sd/roms`, recursively; saves sit next to the ROM.
  Load only the selected native module after choosing a game. A `.gb` ROM's
  CGB flag can select the color core regardless of its extension.
- The console requires a pad, saves and pauses on disconnect, and resumes on
  reconnect. The desk keeps working by touch. Preserve the no-pad waiting
  screen. SELECT+START opens the shared game menu; X+Y has no special meaning.
  Consume the chord before game input; wait for release when closing menus.
- GB/GBC/GG use exact 3× scaling to 480×432 centered in 480×480, with 24px
  black bars; the menu can select centered 1× instead. NES/SMS default to 2×
  with eight source pixels cropped per side. GB/GBC frame scale is 1=3×,
  2=centered 1× (0 retains the diagnostic 240px API); SMS/GG/NES use 2=large,
  1=centered 1×. Do not introduce noninteger stretching into Retro.
  Use `Presto(..., full_res=True, direct_to_fb=True)` to avoid display copies.
  Write 32-bit output rows sequentially, not interleaved halfword stores.
  Compose ROM menus/messages in a separate PicoGraphics buffer, then present
  the complete image; clearing the direct scanout causes visible flicker.
- `device/lib/retro_clock.py` temporarily selects 300 MHz for emulation. Restore
  the original clock for save writes, pad disconnects, exceptions and exit.
  Keep loading/menus at the original clock; preserve original-speed pacing.
  Do not change voltage registers. Validate clock changes on actual hardware
  with framebuffer/PSRAM checks, not only timing benchmarks.
- NES/SMS emulate at their original ~60 Hz and cap display at 30 Hz.
  Allow consecutive CPU-only catch-up frames when rendering overruns; never
  halve emulation speed. Heavy games can display substantially fewer images.
  Native scanline/output buffers use the stack only during frame(); never
  retain stack pointers between calls.
- `native/gb/` is Peanut-GB, `native/gbc/` Walnut-CGB, `native/sms/` TotalSMS
  (GG and SMS), `native/nes/` InfoNES, `native/fbtest/` framebuffer diagnostics.
  Adapters share `init`, `set_ram`, `palette`, `frame`; native-owned cartridge
  RAM has `get_ram` for a live view. SMS init takes a second GG-mode argument.
  Keep the legacy five-argument unscaled 240×240 GB renderer for diagnostics.
  NES caches 32 decoded CHR-ROM banks (128 KiB); never evict active mappings,
  cache writable CHR RAM, or pass cache addresses to mapper PPU callbacks.
  Clear cache metadata and mapped pointers when initializing a new cartridge.
  All cores currently omit audio. NES supports iNES 1 mappers 0,1,2,3,4,7; unsupported CHR configurations are rejected.
- Native BSS arrays must be non-static for `mpy_ld`, initialized tables const.
  Keep vendor licenses and record revisions and modifications in `UPSTREAM.txt`.
  `tests/rom_fixtures.py` contains original video test programs for hardware
  checks, not third-party game data. Keep downloaded games out of git.

## Privacy and local assets

This repository is public. Keep internal hostnames, IP addresses, project
names, credentials, and tokens out of committed code, examples, and logs.

- Never print `device/secrets.py`. It is ignored and contains WiFi, Immich,
  and Home Assistant credentials; use `device/secrets.example.py` as a template.
- `device/ha_config.py` is ignored and contains the HA host and entity IDs;
  use `device/ha_config.example.py` for public configuration examples.
- Pinned pipeline configuration belongs in the plugin config directory's
  `pipelines.json`, not in tracked source.
- Custom `*.rtttl` melodies stay on the device and out of git.
- ROMs (`*.gb`, `*.gbc`, `*.gg`, `*.nes`, `*.sms`), saves (`*.sav`), native build directories, and
  generated native `*.mpy` files are ignored. Preserve these exclusions.

## Firmware, runtime, and performance

- Target Presto firmware **v1.0.0**. The documented device runs MicroPython
  **1.26.0**, build `feature/presto-wireless-august-2025` (2025-08-18).
  v2.0.0 hangs on flash writes (pimoroni/presto#121); do not propose an upgrade
  as a routine fix. Verify the actual device version when relevant.
- MicroPython differs from CPython: avoid `[::-1]` (use `reversed`), and pass
  eight values to `time.mktime`. This firmware has no `_thread`.
- Use `time.ticks_diff` and `time.ticks_add` for deadlines and elapsed time;
  `ticks_ms` wraps after roughly 12 days.
- Create `Presto()` before connecting WiFi: it resets the radio. Preserve
  reconnect logic because the first connection after boot can fail.
- Keep network I/O non-blocking. `lib/haclient.py` spreads requests over
  frames using non-blocking sockets. HA uses plain HTTP on the LAN because
  HTTPS requests take 1–3 seconds.
- Keep UDP reads at least `recv(4096)`; smaller buffers silently truncate
  pipeline messages. Read packets every frame.
- Aim for roughly 30 fps. Movement is time-based (`k = frame time / 66 ms`).
  Avoid allocations and repeated work in the hot loop: constructing a dict
  with a few hundred entries takes about 100 ms on the device.
- Build sprite grids and cached colour runs once (`runs_from_grid`);
  `draw_art` also caches runs. Prefer cheap rectangles for drawing.
- Import names/modules at the top with `from desk.x import name` or
  `from desk.scene import mod`; avoid repeated long attribute chains per frame.

## Desk behavior and art

- Preserve the seven `pages.VIEWS`: scene, today, agents, pipelines, home,
  settings, apps. Other pages redraw only when their data/blink key changes;
  skip `presto.update()` when nothing changes.
- Messy and Clawd are `Actor`s. Reset their `Pose` each frame, then fill it
  through `act()` or the active director. `Ball`, `Duo`, and pirate `Visit`
  control both actors through `update()`, `draw()`, and `mood()`.
- Herdr status drives Clawd (`work`, `alert`, `done`); pipeline status drives
  Messy (`wheel`, `broken`). Directors normally take precedence, but an agent
  asking a question ends `Ball` and `Duo`.
- An actor held by external status must not time out into a random state or
  start a game. Preserve `next_state` handling.
- Between 22:00 and 06:00 (`seasons.bedtime`), actors sleep and games, visits,
  and birds stop. Work status can wake the relevant actor; it sleeps again
  afterward.
- Show Clawd's completion only for `DONE_MS`, restarting for a new completion.
  Show Messy's failed wheel and red pulse only for `BROKEN_MS`, restarting
  on another failure. Herdr's persistent status must not extend these forever.
- Preserve urgency ordering (blocked, working, done, idle), compact page
  layouts, and overflow counts. Pipeline history uses `recent_pipes` and
  `MAX_RECENT`; scene icons respect `PIPE_ROWS` and `AGENT_ROWS`.
- Detect sound events per item (`_watch_agents`, `_watch_pipes`), so one
  completion remains audible while another item is still running.
- Age particles on every page; draw them only on the scene page.
- Settings live in device `settings.json`: `leds`, `anim_leds`, `sounds`,
  `anim`, `music`. Character squeaks (`CHARACTER_SOUNDS`) are deliberately off;
  `sounds` controls status beeps and `anim` controls scene sounds.
- Use chunky pixel art, the PICO-8 palette, and a 4 px grid (Messy's pixels
  are 4 px, Clawd's 5 px). New props and particles use 4 px blocks and movement
  steps through `gfx.draw_colour_art` and `gfx.snap`; omit tiny details.
- `scene/gb_sheet.py` provides Guybrush's original-look sheet; `sprites.py`
  has a fan-art fallback. Sheet props use `GB_HAND`; there is no `GB_ARMS`
  frame or native walk frames. `sprites.py` synthesizes eight cached walk
  poses with leg strides, arm swing, coat and ponytail motion. Keep the
  planted boot on the ground when applying body bob, including at reminder scale.

## Host-side status protocol

- `notify.py` broadcasts combined agent status to UDP **47474** on changes.
- `pipelines.py`, managed by `poller_ctl.py`, polls active Herdr spaces every
  30 seconds using `glab api` / `gh api`. It sends `type: pipelines` and
  repeats agent status. Between polls, cached status and daily notes are
  repeated every 5 seconds with packets spaced out for the device's radio.
- Every message includes `src` (computer name). Keep per-computer state
  separate and merge only for display; closing one host clears only its data.
  Stale agents and pipelines expire after three minutes without updates.
- `usage.py` reads `~/.cache/presto-usage.json`, written by Claude Code's
  status line, and sends `type: usage`. Across hosts, the newest `ts` wins.
- `daynote.py` finds the Obsidian vault through `obsidian.json` or a `daynotes`
  override in `pipelines.json`. It reads `YYYY-MM-DD.md`, `## Termine`
  appointments such as `(13:00)`, and `## Aufgaben` tasks; no note means no
  work day. Its existing sync runs `git pull --ff-only` every five minutes.

## Validation and device workflow

Focused gamepad checks live in `tests/`; run
`python3 -m unittest discover -s tests -v`. There is no central lint configuration.
Use focused checks appropriate to the changed code. Host-side syntax checks
do not establish MicroPython or hardware compatibility. Do not import app
entry points as a syntax check: they can start loops, networking, or hardware.
Test runtime and rendering changes on the Presto when available; report
clearly when hardware validation could not be performed.

`mpremote` is the documented device tool. Discover the actual port with
`timeout 10 mpremote connect list`; the documented port is `/dev/ttyACM0`
(USB ID `2e8a:0005`). Only one client can own it; Thonny or another REPL may
need to be closed. Bound calls with `timeout` so a stalled board cannot hang
the session.

```sh
timeout 20 mpremote fs ls :
timeout 20 mpremote exec "import os; print(os.listdir('/'))"
timeout 20 mpremote fs cp device/foo.py :
timeout 20 mpremote fs cp :foo.py /tmp/
timeout 30 mpremote run device/foo.py
timeout 20 mpremote reset
```

Deploy only the necessary files when device work is in scope. Upload desk
packages before running a local copy of `desk/main.py`, because local runs
use the packages already on the device. Recursive package upload is
`timeout 60 mpremote fs cp -r device/desk device/lib :`; exclude local
`__pycache__` directories first. For loop debugging, run a temporary copy
with debug prints under `timeout 30` and capture its output to a file. The
desk loop normally never exits. A reset loses displayed agent status until
the poller refreshes it (within 30 seconds).

Build native modules against a MicroPython **v1.26.0** source checkout:

```sh
make -C native/gb MPY_DIR=/absolute/path/to/micropython
make -C native/gbc MPY_DIR=/absolute/path/to/micropython
make -C native/sms MPY_DIR=/absolute/path/to/micropython
make -C native/nes MPY_DIR=/absolute/path/to/micropython
make -C native/fbtest MPY_DIR=/absolute/path/to/micropython
```

The Makefiles target `ARCH=armv7emsp` and share
`-fno-tree-loop-distribute-patterns`; preserve firmware compatibility and
shared flags. On NixOS add `MKDIR=mkdir RM=rm` because `dynruntime.mk` expects
`/bin/mkdir`. Upload the resulting module to device `/lib` for hardware tests.
Preserve the upstream MIT license in `native/gb/peanut_gb.h`.
