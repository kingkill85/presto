# Doomgeneric on Presto

Experimental Doom 1.9 shareware app for Presto firmware **v1.0.0** and
MicroPython **1.26.0**. Choose **Spiele → Doom → Doom Shareware** with a Qw/ST
Pad connected. The runtime starts E1M1 at skill 2; Doom's own menu can start
another shareware game. Other IWADs, PWADs and multiplayer are not supported.

## Display and controls

The 320×200 indexed image is displayed at **480×360**, centered with 60-pixel
black bars for the original 4:3 aspect ratio. This uses nearest-neighbour
scaling with uneven pixel sizes. The shared menu also offers centered 320×200.
The game palette is restored after every menu, including damage flashes.

- D-pad: move and turn; hold **X** while moving left/right to strafe.
- **A**: fire; **B**: use/open; **Y**: cycle owned weapons.
- **Start**: Enter; **Select**: Doom's original menu.
- **Select + Start**, or tap the top black border: shared game menu.

The shared menu provides five native Doom save slots, zoom, volume, restart
and return to the library. Saves use Doom's level/player/world archive, not
an emulator snapshot; music restarts when loading. Each slot has a versioned
core ID, IWAD identity and checksum, checked before native restore. Engine
pointer fields are stored as presence flags or original archive indices.
A pad disconnect releases held keys, pauses and writes a separate automatic
save. Reconnecting resumes; the next launch offers that automatic save.

DMX sound effects and MUS music with GENMIDI instruments play through the
piezo. Music uses emu8950's nine-channel YM3812 synthesis at half the chip rate
(24,858 Hz, two chip steps per sample; pitch and envelopes keep their timing),
resampled to 22,050 Hz. Silent released voices are skipped. This is a compact driver, not a bit-exact
reproduction of every original AdLib driver detail. The runtime shares the
verified P8/SRAM PWM queue with SCUMM: scanout owns the first framebuffer
half, audio owns buffers in the second. Menus and SD save writes pause audio
before restoring the boot clock. Gameplay temporarily uses 300 MHz through
`retro_clock`, without voltage changes.

## Build and installation

Use ARM embedded GCC, GNU make, Python, pyelftools and a MicroPython v1.26.0
source checkout:

```sh
git clone https://github.com/ozkl/doomgeneric.git /tmp/doomgeneric
git -C /tmp/doomgeneric checkout e257a09527062bfb986b6e5e0780839b6cbd5b71
python3 native/doom/build.py --source /tmp/doomgeneric --mpy-dir /path/to/micropython-v1.26.0
```

`CROSS_COMPILE` can specify the toolchain prefix. The build requires the pinned,
unmodified upstream checkout. It uses the SCUMM section conversion helper,
but does not require a compiled SCUMM engine. Keep the vendored MIT license
and upstream Doom GPL license with distributions.

Install `doomcore.mpy` in device `/lib`, `device/doom.py` in `/`, and the
repository's matching `device/lib` and `device/desk` packages. The shared
launcher, game menu, audio, gamepad and save helpers are required.
Place legally obtained Doom 1.9 shareware data at `/sd/doom/doom1.wad` (uppercase
`DOOM1.WAD` is also recognized). The runtime checks SHA-256:

```
1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771
```

The tested IWAD is 4,196,020 bytes with 1,264 directory entries. Game data and
compiled modules are excluded from Git. Discovery checks file size without
loading the native engine; the runtime checks the complete IWAD before use.
Saves live in `/sd/saves/doom-<path-hash>/`, with a separate `-disconnect`
directory for the automatic save.

Doom's 320×200 drawing buffer and its COLORMAP light tables (72,704 bytes)
live in on-chip SRAM: the P8 framebuffer's second half after the two 32 KiB
audio queue buffers (about 160 KiB, otherwise unused; firmware v1.0.0
`update()` only sets the palette in P8 mode). Everything else uses PSRAM.
The core uses a 5 MiB Python-owned arena, including Doom's 4 MiB zone. Allocate
it before loading the UI/core to avoid heap fragmentation. Keep the arena,
callback and display alive until reset: native pointers are not GC roots.
Initialize once per MicroPython session; restart through the launcher/reset.

## Validation and current limits (2026-11-06)

Tested on physical Presto, MicroPython 1.26.0 build
`feature/presto-wireless-august-2025` (2025-08-18), with Qw/ST Pad:

- E1M1 loads and accepts movement/fire. A captured indexed framebuffer and its
  palette confirm correct colours and the centered 480×360 output.
- With music/effects enabled, 15 seconds of E1M1 while walking and turning
  show approximately **28 distinct frames/s** (431–448), without audio
  underruns; standing still reaches the 35 tic/s limit. The first version
  showed about 12 fps with six underruns. Measured steps (distinct frames
  while moving, 15 s): 357 after the half-rate OPL and idle voices (music
  synthesis 68% → 30% of the time), 397 with the tic wait fix, 448 with SRAM. The simulation targets 35 tics/s and skips rendering during
  catch-up. Heavy scenes may still fall behind; this is experimental.
- The most recent ten-second audio profile reported two queue underruns;
  audible continuity is not guaranteed. The piezo's subjective sound quality
  has not been independently confirmed.
- Native save/load restores map, health and position after movement. The
  reproducible five-slot test below passed both writing distinct positions and
  restoring all five after a fresh MicroPython session, including clock
  restoration around writes and exit.
- All 118 repository tests passed. Host tests exercise allocation bounds, every RGB565/P8 output pixel, zoom,
  untouched audio-buffer guards, synthetic MUS/DMX playback, bounded malformed
  music streams, menu-chord handling and corrupted-save rejection. Sound tests
  run ASan/UBSan and require the pinned checkout (`DOOMGENERIC_DIR`, default
  `/tmp/presto-doomgeneric`). No third-party game data is used by host tests.

Run the finite save check twice with the deployed runtime and a connected pad.
It writes only `/sd/saves/doom-hardware-test`, separate from player slots:

```sh
timeout 60 mpremote connect /dev/ttyACM0 run native/doom/check_runtime.py
timeout 60 mpremote connect /dev/ttyACM0 exec 'DOOM_CHECK_RESTORE=True' + run native/doom/check_runtime.py
timeout 20 mpremote connect /dev/ttyACM0 reset
```

`probe.py` retains the earlier silent RGB565 diagnostic, with optional PSRAM
pattern verification. Its historical 300 MHz result was 212 frames/351 game
tics in 10,013 ms (~21 fps); this is **not** the audio-enabled app's performance.
The 1 MiB PSRAM pattern survived that short run unchanged, and the clock
returned to 200 MHz. Neither diagnostic replaces device firmware.

## Alternative engine: rp2040-doom compatibility check (2026-11-06)

This was a source review plus an on-device memory-layout probe, **not an
rp2040-doom gameplay run or FPS benchmark**. The optimized upstream build
cannot be loaded unchanged alongside Presto firmware v1.0.0.

Pinned sources:

- [rp2040-doom 29a453c](https://github.com/kilograham/rp2040-doom/tree/29a453c980918a03e40fc8b69b024e7a3bdb5dc2)
- [Presto firmware v1.0.0, 4026e15](https://github.com/pimoroni/presto/tree/4026e1541514958f34e5c6e44b6815c7e6a22135)

Reproduce the read-only device probe, then return to the desk:

```sh
timeout 20 mpremote connect /dev/ttyACM0 run native/doom/rp2_compat_probe.py
timeout 20 mpremote connect /dev/ttyACM0 reset
```

Findings:

1. **The optimized build's short-pointer window overlaps active scanout.**
   `src/doomtype.h` encodes RP2350 pointers as 16-bit, four-byte offsets from
   `0x20030000`, accepting addresses below `0x20070000`. The live Presto
   RGB565 framebuffer starts at `0x20000c00`, length 460,800 bytes, ending
   at `0x20071400`. The entire 262,144-byte short-pointer window is inside it.
   The probe's arena was at `0x110385a0` in PSRAM; the hypothetical short-pointer
   conversion reconstructs `0x200385a0`, not the original pointer. The probe
   checks this arithmetic without calling the upstream breakpoint or
   dereferencing that invalid result. Do not place an engine heap in scanout.
2. **Core 1 already belongs to the display.** Firmware
   `modules/c/presto/presto.cpp` launches `presto_core1_entry`, which services
   display interrupts. Upstream `src/pico/i_video.c` independently launches
   its own core 1 entry, VGA scanvideo and interrupt handler.
   `src/pd_render.cpp` schedules flat/column work and audio on that core.
3. **Audio is not a ready-made Presto backend.**
   `src/pico/i_picosound.c` uses Pico I2S audio with explicit DMA channel 6
   and PIO state machine 0; our piezo needs a compatible PWM backend.
   The existing sound engine is useful source material, but its hardware
   setup must be replaced, not executed as-is.
4. **Startup changes hardware policy.** `src/i_main.c` changes the voltage,
   system clock and RP2350 QMI timing. Our module must omit that startup and
   retain `retro_clock`, firmware flash/PSRAM settings and display ownership.
5. **The optimized data path differs.** `USE_WHD`/`USE_MEMORY_WAD` consume
   converted WHD/WHX data through mapped addresses. SD streaming of the raw
   WAD through our existing Doomgeneric callback is not a drop-in backend.

A native port is possible in principle by replacing pointer assumptions,
serializing renderer work, implementing the Presto display/audio backends and
loading converted data into owned memory. These changes also remove or alter
parts of the configuration behind upstream's advertised frame rates. It would
be misleading to benchmark the unoptimized desktop fallback and present that
as the optimized RP2350 port.

**Decision:** retain the working Doomgeneric prototype for the current
firmware. The alternative has not demonstrated a speed or sound advantage
on this Presto. A complete adaptation is a separate porting effort; no claim
is made that it would be slower or impossible. The compatibility check did
not replace firmware, launch another core, change IRQ/DMA ownership, or
write voltage/clock registers.
