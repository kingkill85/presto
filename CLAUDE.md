# CLAUDE.md

MicroPython apps for the Pimoroni Presto (RP2350, 480×480 touch screen).
See README.md for what each file does.

## Talking to the device

- Connected via USB at `/dev/ttyACM0` (USB ID `2e8a:0005`, "MicroPython Board in FS mode").
- Use `mpremote` (installed). Check the connection with `mpremote connect list`.
- Only one client can hold the serial port: close Thonny or any open REPL first.
- Wrap calls in `timeout` so a hanging device doesn't block, e.g.
  `timeout 20 mpremote exec "import os; print(os.listdir('/'))"`.

Common commands:

```sh
mpremote exec "..."                 # run code on the device
mpremote fs ls :                    # list files on the device
mpremote fs cp device/foo.py :      # upload
mpremote fs cp :foo.py /tmp/        # download
mpremote reset                      # reboot (starts the start screen)
mpremote run device/foo.py          # run a local file without uploading
```

To test the start screen, run a copy of `desk/main.py` with debug prints via
`timeout 30 mpremote run <copy>` and redirect the output to a file (the
script never ends; `mpremote run` uses the `desk/` package already on the
device, so upload that first). Upload with
`mpremote fs cp -r device/desk device/lib : + reset`. Don't copy local
`__pycache__` folders to the device.
A restart loses the agent status until the next poller round (≤30 s).

## Layout and conventions

- Everything in `device/` goes to the root of the device's filesystem.
- The repo is public: keep internal host names, IPs, project names and
  tokens out of it.
  - `device/secrets.py` (WiFi, Immich, `HA_TOKEN`) is gitignored, template
    `secrets.example.py`. Never print it.
  - `device/ha_config.py` (HA host and entity ids) is gitignored, template
    `ha_config.example.py`.
  - Pinned pipelines live in the plugin's config dir (`pipelines.json`).
  - `*.rtttl` melodies (e.g. `guybrush.rtttl`) stay on the device only.
  - `device/desk/scene/gb_sheet.py`: Guybrush in the original look, made
    from a sprite sheet; without it `sprites.py` draws our own fan art. Props use `GB_HAND`, the sheet has no
    arms-up frame (`GB_ARMS`) and no walk frames. `sprites.py` synthesizes
    eight cached walk poses with strides, arm swing, body bob, coat and ponytail motion.
- Root: only apps, config and `sdcard.py`. Shared helpers go to `lib/` (on
  `sys.path`, so `import tz` works). Exception: `sdcard.py` stays in the root,
  since `.frozen` (with the broken built-in `sdcard`) comes before `/lib`.
- `main.py` just imports `desk.main`, the start screen (the current focus).
  `desk/` is the whole start screen app; Messy the hamster is only one of its
  characters.
- The start screen is also the launcher: its apps page (`desk/apps.py`) shows
  every `*.py` in the root except `HIDDEN` (config and `sdcard.py`); new
  helpers go to `lib/` instead. A tap writes the file name to
  `/ramfs/launch.txt` and resets, `main.py` starts that app once (it removes
  the file), so the next reset is back on the start screen.
- SD card is mounted at `/sd` using our own `sdcard.py` (the built-in driver
  fails with v2 cards).
- `lib/tz.py` turns the UTC time from `ntptime` into German local time (CET/CEST).
- `lib/gamepad.py` handles the optional Qw/ST Pad on external I2C (SDA 40,
  SCL 41), shared by desk navigation and Game Boy. The desk keeps touch without
  a pad. Game Boy requires the pad, uses exact 3x scaling (480x432 centered
  on 480x480 with 24px black bars) without touch controls,
  saves and pauses on disconnect, and resumes on reconnect. Reconnect is
  retried once per second; held keys are released on disconnect.
  Run `python3 -m unittest discover -s tests -v` for focused input checks.

## The start screen (desk/)

- `desk/main.py`: main loop (touch, status overrides, poses, drawing, LEDs).
  `desk/`: `gfx` (screen, palette, helpers), `prefs`, `sound`, `leds`,
  `pages` (other pages), `apps` (app list and launch).
  `desk/data/`: `herdr` (UDP status and the daily note), `ha` (Home Assistant).
  `desk/scene/`: `scene` (main page), `sprites` (characters), `actors` (state
  machines and `Pose`), `directors` (`Ball`), `duo` (`Duo`, scenes
  for two), `pirate` (`Visit`: Guybrush's visits, one of `KINDS` each time, rare: `EVERY_MS`), `seasons` (meadow, seasonal particles, holidays), `particles`,
  `critters` (bird, snail), `reminder` (Guybrush before an appointment).
- Import with `from desk.x import name` or `from desk.scene import mod` at the
  top, so the hot loop only does one lookup (no `desk.scene.x.y` chains per frame).
- Seven swipe pages (`pages.VIEWS`): scene, today, agents, pipelines, home, settings, apps.
  The pages other than the scene are only redrawn when their key (data plus
  a blink tick) changes, and `presto.update()` is skipped otherwise.
- Messy and Clawd are `Actor`s with a state machine (`start`, random `pick`).
  Each frame their `Pose` is reset, filled by `act()` for their own states,
  then by the director if one runs. Directors (`Ball`, `Duo`, `Visit`) take
  over both: `update()` moves and poses them, `draw()` adds extras, `mood()`
  sets the LEDs. External status overrides states: Herdr agents → Clawd
  (`work`, `alert`, `done`), pipelines → Messy (`wheel`, `broken`), but never
  during a director (an agent asking a question ends `Ball` and `Duo`).
- From 22:00 to 6:00 (`seasons.bedtime`) both just sleep: no games, scenes,
  pirate or bird. Herdr work still wakes them (Clawd for agents, Messy for
  pipelines); afterwards they go back to sleep.
- While a status wants an actor (wheel, laptop), its state never times out into
  a random pick, so no game or scene can start over it (`next_state`).
- Clawd shows `done` for `DONE_MS` only (again when another agent finishes):
  Herdr keeps an agent "done" until you look at it, maybe for hours.
- After a failed pipeline Messy sits in the broken wheel (and the LEDs pulse
  red) for `BROKEN_MS` only, then gets out; another failure starts it again.
- Left of the clock: one icon per pipeline that ran since boot, with its last
  status (`herdr.recent_pipes`, max `MAX_RECENT`, oldest finished drop out),
  in two columns of `PIPE_ROWS` (the wheel's rim is below).
  Right of the clock: one icon per agent in up to two columns of
  `AGENT_ROWS` (above Clawd's head), beyond that one per status with the number.
- `herdr._merge` sorts the agents blocked, working, done, idle, so wherever
  only the first few fit (AGENTS page, icons, LEDs) the urgent ones show.
  The AGENTS page (`agent_layout`) gives every agent a full row while they
  fit, then puts the idle ones into one shared line, then shrinks the rows to
  one line, and counts the rest in a "+N" line.
  The PIPELINES page (`pipe_layout`) does the same: passed (and canceled)
  ones share a line, the others get one line each with their space.
- Movement is time based (`k` = frame time / 66 ms), target ~30 fps. Use
  `time.ticks_diff`/`ticks_add` for times, `ticks_ms` wraps after ~12 days.
- Particles age on every page (`particles.update`), but are only drawn
  on the scene.
- Beeps come from per-item changes (`herdr._watch_agents`, `_watch_pipes`), not from the combined status, so one agent or pipeline finishing while another still runs is heard.
- Settings (`leds` = status LEDs, `anim_leds` = mood and scene lights, `sounds`, `anim`, `music`) are in `settings.json` on the device.
  Character squeaks (`sound.CHARACTER_SOUNDS`) are deliberately off; `sounds` only
  covers pipeline and Claude beeps, `anim` the scene sounds (fight).

Style: everything is chunky pixel art on a 4 px grid (Messy 4 px, Clawd 5 px
pixels). New art, props and particles use 4 px blocks (`gfx.draw_colour_art`,
`gfx.snap`) and move in 4 px steps; leave out details too small for that.

MicroPython gaps that bit us: no `[::-1]` (use `reversed`), `time.mktime`
takes 8 values. Test on the device, not only in CPython.

Performance on the Presto (measured, keep in mind when adding things):

- Building a dict with a few hundred entries takes ~100 ms. Sprites are built
  once into grids, turned into colour runs (`runs_from_grid`) and cached; small
  art goes through `draw_art`, which caches runs too. Rectangles are cheap.
- Connect WiFi only after `Presto()` is created (it resets the radio), and
  retry: the first attempt right after boot can fail (`keep_wifi`).
- There is no `_thread` in this firmware. Network I/O must not block:
  `lib/haclient.py` spreads each HTTP request over frames with non-blocking
  sockets. HTTPS to HA takes 1-3 s per request, so it uses plain HTTP on the LAN.
- UDP packets from the PC are read with `recv(4096)`; the pipeline list is
  ~1 KB and a smaller buffer silently drops it.

## PC side (herdr-plugin/)

- `notify.py` runs on every Herdr agent status change and broadcasts the
  combined status to UDP port 47474.
- `pipelines.py` (started and kept alive by the plugin via `poller_ctl.py`)
  polls the CI of the active Herdr spaces (GitLab via `glab api`, GitHub via
  `gh api`) every 30 s and sends it on the same port with
  `"type": "pipelines"`, plus the agent status again.
- Every message carries the computer's name (`"src"`); the Presto keeps each
  computer's agents, pipelines and daily note apart and shows them merged
  (`herdr._merge`), so Herdr can run on several computers at once. Closing
  Herdr on one only removes its part.
- Between the 30 s rounds the poller sends the agent status and the last
  pipelines and daily note again every 5 s (spaced out: the Presto's radio
  only buffers a few packets, it reads them every frame). Broadcasts get lost
  now and then, the repeats make up for it.
- `usage.py` (called by the poller) reads Claude's limits from
  `~/.cache/presto-usage.json`, which the user's Claude Code status line
  writes (it is the only place Claude Code exposes `rate_limits`), and sends
  `"type": "usage"`. The Presto takes the newest `ts` of all computers and
  shows it in a slim tile at the bottom of the AGENTS page.
- `daynote.py` (called by the poller) reads today's note `YYYY-MM-DD.md` from
  the Obsidian vault (found via Obsidian's `obsidian.json`, so it works on every
  computer; setting `daynotes` in `pipelines.json` overrides it), `git pull
  --ff-only`s the vault every 5 min and sends `"type": "day"` with appointments
  (`## Termine`, a time like `(13:00)`) and tasks (`## Aufgaben`). No note means
  no work day (weekend, holiday).

## Firmware

- Target firmware is Presto **v1.0.0**. v2.0.0 hangs on every flash write
  (pimoroni/presto#121), so don't suggest upgrading.
- Firmware currently on the device: MicroPython 1.26.0, build
  `feature/presto-wireless-august-2025` (2025-08-18).

## Retro console

`device/gb.py` is now a thin entry point for `lib/retro.py`, one ROM list for
GB, GBC, GG, NES and SMS. `retro_roms.py` discovers supported files recursively
under `/roms` and `/sd/roms` and imports only the selected core. `.gb` files
with the CGB header flag select the color core. Kernels: Peanut-GB (`native/gb`),
Walnut-CGB (`native/gbc`), TotalSMS (`native/sms`, both GG/SMS), InfoNES
(`native/nes`, mappers 0/1/2/3/4/7). Exact revisions, licenses and local patches
are recorded next to each native core. All currently omit audio.
NES/SMS cap display at 30 Hz while emulating at ~60 Hz. Additional images are
skipped on missed deadlines; demanding games can display substantially fewer
images. Native scanline/output scratch buffers live on the stack for frame()
only; no stack pointer may survive the call.
Handhelds use 3x integer scaling (480x432); NES/SMS default to 2x with eight
source pixels cropped per side. Y toggles the complete centered 1x image. All use
direct framebuffer writes. Pad disconnect saves and pauses; SELECT+START opens the shared game menu.
Only games.py is visible; virtual folders route gb.py/scumm.py after reset.
The desk remains touch-controlled without a pad. ROMs and saves stay out of git.
