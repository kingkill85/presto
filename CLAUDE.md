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
mpremote reset                      # reboot (starts hamster.py)
mpremote run device/foo.py          # run a local file without uploading
```

To test `hamster.py`, run a copy with debug prints via
`timeout 30 mpremote run <copy>` and redirect the output to a file (the
script never ends; `mpremote run` uses the `messy/` package already on the
device, so upload that first). Upload with
`mpremote fs cp -r device/messy : + fs cp device/hamster.py : + reset`.
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
- `main.py` just imports `hamster.py` (Messy the pixel hamster, the current
  focus). `hamster.py` is only the main loop; the rest lives in the package
  `device/messy/` (a folder, so the launcher doesn't list its modules).
- `launcher.py` is the parked launcher. It shows every `*.py` in the root
  except the names in `HIDDEN`; a new helper module (not an app) must be added
  there. To launch an app it writes the file name to `/ramfs/launch.txt` and
  resets. It only works as `main.py`, since it relies on running at boot.
- SD card is mounted at `/sd` using our own `sdcard.py` (the built-in driver
  fails with v2 cards).
- `tz.py` turns the UTC time from `ntptime` into German local time (CET/CEST).

## hamster.py and messy/

- `hamster.py`: main loop (touch, status overrides, poses, drawing, LEDs).
  `messy/`: `gfx` (screen, palette, helpers), `sprites` (characters),
  `actors` (state machines and `Pose`), `directors` (`Ball`, `Visit`) and
  `duo` (`Duo`, scenes for two), `scene` (main page, particles), `pages`
  (other pages), `herdr` (UDP status), `home` (Home Assistant), `sound`,
  `leds`, `prefs`.
- Five swipe pages (`pages.VIEWS`): scene, agents, pipelines, home, settings.
  The pages other than the scene are only redrawn when their key (data plus
  a blink tick) changes, and `presto.update()` is skipped otherwise.
- Messy and Clawd are `Actor`s with a state machine (`start`, random `pick`).
  Each frame their `Pose` is reset, filled by `act()` for their own states,
  then by the director if one runs. Directors (`Ball`, `Duo`, `Visit`) take
  over both: `update()` moves and poses them, `draw()` adds extras, `mood()`
  sets the LEDs. External status overrides states: Herdr agents → Clawd
  (`work`, `alert`, `done`), pipelines → Messy (`wheel`, `broken`), but never
  during a director (an agent asking a question ends `Ball` and `Duo`).
- Movement is time based (`k` = frame time / 66 ms), target ~30 fps. Use
  `time.ticks_diff`/`ticks_add` for times, `ticks_ms` wraps after ~12 days.
- Particles age on every page (`scene.update_particles`), but are only drawn
  on the scene.
- Beeps come from per-item changes (`herdr._watch_agents`, `_watch_pipes`), not from the combined status, so one agent or pipeline finishing while another still runs is heard.
- Settings (`leds` = status LEDs, `anim_leds` = mood and scene lights, `sounds`, `anim`, `music`) are in `settings.json` on the device.
  Character squeaks (`sound.CHARACTER_SOUNDS`) are deliberately off; `sounds` only
  covers pipeline and Claude beeps, `anim` the scene sounds (fight).

Performance on the Presto (measured, keep in mind when adding things):

- Building a dict with a few hundred entries takes ~100 ms. Sprites are built
  once into grids, turned into colour runs (`runs_from_grid`) and cached; small
  art goes through `draw_art`, which caches runs too. Rectangles are cheap.
- Connect WiFi only after `Presto()` is created (it resets the radio), and
  retry: the first attempt right after boot can fail (`keep_wifi`).
- There is no `_thread` in this firmware. Network I/O must not block:
  `haclient.py` spreads each HTTP request over frames with non-blocking
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

## Firmware

- Target firmware is Presto **v1.0.0**. v2.0.0 hangs on every flash write
  (pimoroni/presto#121), so don't suggest upgrading.
- Firmware currently on the device: MicroPython 1.26.0, build
  `feature/presto-wireless-august-2025` (2025-08-18).
