# presto

My own apps for the [Pimoroni Presto](https://shop.pimoroni.com/products/presto)
(RP2350, 4" touch screen, MicroPython).

Runs on Presto firmware **v1.0.0**. v2.0.0 hangs on every flash write
([pimoroni/presto#121](https://github.com/pimoroni/presto/issues/121)).

## Files

Everything in `device/` goes to the root of the Presto's filesystem.

| File | What it does |
| --- | --- |
| `main.py` | Boots straight into `hamster.py`. |
| `hamster.py` | Messy, a pixel hamster desk pet, and Clawd (the Claude Code mascot). See below. |
| `haclient.py` | Non-blocking Home Assistant REST client (one small step per frame). |
| `ha_config.example.py` | Template for `ha_config.py`: Home Assistant host and which entities to show. |
| `launcher.py` | Pixel-art launcher (currently not started at boot): 240×240, PICO-8 palette, 3×3 tiles, swipe between pages. Lists every `*.py` except the helpers in `HIDDEN`. |
| `immich_frame.py` | Photo frame showing random photos from Immich, cached on the SD card. |
| `tz.py` | German local time (CET/CEST) from the UTC set by `ntptime`. |
| `sdcard.py` | SD card driver from micropython-lib ([PR #765](https://github.com/micropython/micropython-lib/pull/765), MIT). Replaces the built-in one, which fails with "timeout waiting for v2 card" ([pimoroni/presto#79](https://github.com/pimoroni/presto/issues/79)). |
| `secrets.example.py` | Template for `secrets.py` (WiFi, Immich URL and API key, Home Assistant token). |

The other apps the launcher shows are Pimoroni's examples from the firmware.

## Messy and Clawd

A 240×240 pixel scene in the PICO-8 palette, running at about 30 fps.

- **Messy** (the hamster) idles, sniffs, looks around, walks, eats seeds,
  washes and sleeps. **Clawd** waves, thinks and walks. Tap either one: it
  cheers (or wakes up) and shows its name.
- **Together** they play catch and act out little scenes: a fight in a dust
  cloud that ends in a hug, a chase around the world, a dance party, sharing a
  snack, leapfrog.
- **Guybrush** (Monkey Island 2 style fan art) walks in every few minutes
  while neither of them is working, shouts "BUH!" and scares both off. He brings a jingle, or your own melody
  from `guybrush.rtttl` (RTTTL ringtone format, git-ignored) on the Presto.
- **Background:** a big pixel clock with weekday and date (NTP), the current
  weather below it, a weather symbol in the corner, a sky colour that follows
  the daylight and a meadow that changes with the seasons.
- **Mood LEDs** on the back follow what's going on.

Swipe left or right through five pages:

1. the scene
2. **AGENTS**: the coding agents in Herdr and their status
3. **PIPELINES**: CI pipelines of the active Herdr spaces
4. **HOME**: Home Assistant weather, rooms, lights, heating, low batteries
5. **SETTINGS**: switch status LEDs, animation lights, sounds, animation sounds and music on or off (saved in
   `settings.json` on the Presto)

## Home Assistant

`device/haclient.py` fetches entity states from Home Assistant over plain HTTP
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
get one agent each (coral = working, green = done, blinking orange = waiting).

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
on workspace focus if needed; it exits when Herdr goes away. Control it with
the plugin actions `presto.clawd.pipelines-start|stop|restart|status`.
Settings go into `$(herdr plugin config-dir presto.clawd)/pipelines.json`:

```json
{"interval": 30, "pinned": [{"host": "gitlab.example.com", "project": "group/project", "ref": "develop"}]}
```

Without `"pinned"` only the spaces are shown. Needs `glab`/`gh` logged in.

## Deploy

```sh
cp device/secrets.example.py device/secrets.py      # fill in, never commit
cp device/ha_config.example.py device/ha_config.py  # optional: Home Assistant
mpremote fs cp device/*.py :
mpremote fs cp guybrush.rtttl :                     # optional: your own melody
mpremote reset
```
