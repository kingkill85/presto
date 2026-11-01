# presto

My own apps for the [Pimoroni Presto](https://shop.pimoroni.com/products/presto)
(RP2350, 4" touch screen, MicroPython).

Runs on Presto firmware **v1.0.0**. v2.0.0 hangs on every flash write
([pimoroni/presto#121](https://github.com/pimoroni/presto/issues/121)).

## Files

Everything in `device/` goes to the root of the Presto's filesystem.

| File | What it does |
| --- | --- |
| `main.py` | Pixel-art launcher: 240×240, PICO-8 palette, 3×3 tiles, swipe between pages. Lists every `*.py` except the helpers in `HIDDEN`. |
| `immich_frame.py` | Photo frame showing random photos from Immich, cached on the SD card. |
| `tz.py` | German local time (CET/CEST) from the UTC set by `ntptime`. |
| `sdcard.py` | SD card driver from micropython-lib ([PR #765](https://github.com/micropython/micropython-lib/pull/765), MIT). Replaces the built-in one, which fails with "timeout waiting for v2 card" ([pimoroni/presto#79](https://github.com/pimoroni/presto/issues/79)). |
| `secrets.example.py` | Template for `secrets.py` (WiFi, Immich URL and API key). |

The other apps the launcher shows are Pimoroni's examples from the firmware.

## Deploy

```sh
cp device/secrets.example.py device/secrets.py   # fill in, never commit
mpremote fs cp device/*.py :
mpremote reset
```
