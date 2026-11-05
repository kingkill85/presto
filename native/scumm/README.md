# Experimental SCUMM-v4/v5 port for Presto

Two explicit German DOS profiles are available under **Spiele → Adventures**:

| Game | Profile | SD directory | Required files |
| --- | --- | --- | --- |
| Monkey Island VGA | 1 | `/sd/scumm/monkey-vga-de` | `000.LFL`, `901.LFL`–`904.LFL`, `DISK01.LEC`–`DISK04.LEC` |
| Monkey Island 2 | 2 | `/sd/scumm/monkey2-de` | `MONKEY2.000`, `MONKEY2.001` |

Lowercase filenames work. The app lists complete installations, with MI2 first.
Select with the D-pad and A, or touch a row; B or the lower touch button returns.
The menu is composed off-screen before presentation to avoid scanout flicker.
The former Atlantis demo was removed at the user's request, including its
launcher/native profile and installed data. Profile 0 is rejected.

This is not the general ScummVM launcher. Other editions, engines and formats
are not advertised as supported. AdLib music and effects use the built-in piezo.
The shared menu exposes native SCUMM slots 1–5 when game scripts allow them.
Write access is restricted to `/sd/scumm/saves`; writes are staged and renamed
on close, retaining a recovery copy during replacement. Game files stay out of git; DOS EXEs and CD images are not used.

## Controls and presentation

- Complete 320×200 image enlarged to **480×300** with nearest-neighbour sampling.
  No blur/cropping; 1.5× necessarily gives uneven pixel sizes.
- The shared menu toggles exact centered 320×200 and the enlarged view.
- D-pad moves the pointer; **A / B** are left/right mouse buttons.
- **X** sends Escape (skip cutscene), **Y** Space (pause), **START / +** Enter.
- **SELECT+START** opens the common pause/save/load/zoom/restart/library menu.
- Touch works without a pad: tap the game to click, or the upper black border
  for the same menu. The engine clock pauses while the menu is open.

`device/scumm.py` is the one-shot app entry. Each native session requires reset:
engine globals retain arena pointers. Exit returns to the game library via reset; restart relaunches the same game. Explicit diagnostic launches use `run(path=..., profile=1 or 2)`.

## Audio and display ownership

The 22,050 Hz stereo mixer is downmixed to mono. Samples are repeated twice for
44,100 Hz PWM on GPIO43, keeping the carrier above the audible band without
speeding up music. Per-block peak measurement bounds amplification with headroom;
volume remains independent (0/30/60/100%, default 100% for SCUMM). The menu stops
DMA before its controls/save actions and resumes only after returning to the game,
including after saving or loading.
Exit and exceptions abort DMA before releasing it.

On **Presto v1.0.0**, the static 460,800-byte SRAM framebuffer has two halves in
full-resolution P8 mode. The native indexed renderer writes the first half
(scanout), and audio owns 65,536 bytes of the unused second half. The driver stays
alive throughout. The layout is checked before constructing non-owning views;
this is firmware-specific, not an allocator for arbitrary SRAM addresses.
The 256 original palette entries and both zoom modes are preserved. Menu canvases
also use P8; returning restores the game palette. The RGB565 diagnostic renderer
remains available. Do not copy a full picture into the audio-owned backbuffer.

Two finite DMA buffers hold roughly 186 ms each to bridge SD/resource stalls.
Each safe callback mixes only one 1024-sample chunk to avoid long animation stalls.
Mixing is cooperative at screen updates, event polling and bounded delay chunks;
there are no new audio IRQs. Delay deadlines include time spent mixing. PSRAM DMA
caused horizontal display artifacts in A/B hardware tests; reducing sample rate
did not fix them and made the PWM carrier audible. SRAM output eliminated the
initially reported lines, but intermittent lines reappeared in longer play.
The four verified PIO1 display DMA channels therefore receive temporary high
priority while audio runs; their previous priority is restored on pause/exit.
Only the priority bit in the non-triggering control alias changes, after checking
the live display-chain mapping. No channel is reclaimed or aborted and no display
IRQ is changed. The follow-up interactive test no longer showed noticeable lines.
The engine runs at 300 MHz (`retro_clock`); menus and save writes return to
the boot clock with audio paused. MI2 measured 2582 instead of ~2090 frames in
90 s; underruns (5) stayed the same, they follow SD room loads.
Rare underruns during loading can still cause brief interruptions;
this is not a full playthrough validation. Interactive MI2 checks ran for three
minutes, including controls, with 4–7 queue underruns; the subsequent two-minute
priority check recorded eight. Isolated native save/load checks passed for both
profiles and confirmed audio resumed after loading. The host suite covers gain
headroom, chunk scheduling, menu cleanup and priority restoration, in addition
to the exact RGB565/P8 renderer fixture.

Interactive check (intro skipped, three minutes by default):

```sh
timeout 205 mpremote exec "PROFILE=2" + run tests/check_scumm_audio_device.py
```

## Build

Requires ARM embedded GCC C/C++, make, Python with `pyelftools`, and a
MicroPython **v1.26.0** checkout with `mpy-cross` built. Tested with ARM GCC 15.2.
The target is the existing Presto v1.0.0 firmware; no firmware replacement or
CPU-frequency change is required. Device tests use the normal 200 MHz.

From this directory:

```sh
mkdir -p build
git clone https://github.com/rh1tech/frank-quest.git build/frank-quest
git -C build/frank-quest checkout 949301b6ef87a5482340167378cd102fcdb82ef2
make MPY_DIR=/path/to/micropython MKDIR=mkdir RM=rm
python build_engine.py --source build/frank-quest --mpy-dir /path/to/micropython
```

The first make builds the runtime probe and fixed-arena allocator; the second
command builds `scummcore.mpy`. `SCUMM_DIR=/path/to/frank-quest` selects an
existing checkout for make. The engine builder requires the exact clean
upstream revision. Generated sources, objects and native modules remain ignored.
Licenses stay in generated copies; transformations are recorded in `UPSTREAM.txt`.

The module occupies about 1.04 MB native text/data and uses a caller-owned
4 MiB arena. These are allocations, not measured minimum game requirements.
The 187 C++ source build includes the engines, supporting libraries and OSystem;
our C/MicroPython backend supplies the device interfaces.

### Native loader constraint

MicroPython 1.26 loads native data into writable, rooted RAM. `prepare_data.py`
puts initialized C++ data there; `--ram-bss` also places zero-filled engine
statics in that image so local PC-relative references resolve. The zero image
and on-device engine behavior were checked. **Not flash-loader compatible.**
Static constructors/destructors are rejected before section GC can discard them.
Allocation, including newlib's reentrant variants, uses the fixed arena.

## Installation and edition checks

Copy your game files to the directories above, then from the repository root:

```sh
timeout 120 mpremote fs cp native/scumm/scummcore.mpy :/lib/scummcore.mpy
timeout 20 mpremote fs cp device/lib/scumm_files.py device/lib/scumm_backend.py device/lib/scumm_audio.py device/lib/retro_audio.py :/lib/
timeout 20 mpremote fs cp device/scumm.py :/scumm.py
timeout 20 mpremote fs cp device/desk/apps.py :/desk/apps.py
timeout 20 mpremote reset
```

Only one serial client may own the board. The app mounts SD itself and makes
its saves directory. The index SHA256 is checked before starting native code;
the corresponding upstream MD5 identifier is passed to the engine. This firmware
has SHA256 but no `hashlib.md5`. Edition hashes are recorded in `UPSTREAM.txt`.

The supported MI1 index is the German VGA edition from Bestseller Games 02
(8357 bytes); MI2 is the German DOS edition from Bestseller Games 07 (11135 bytes).
All installed game data are verified against the user's local source files.

## Validation

```sh
python3 -m unittest discover -s tests -v
cc -std=c11 -O2 -Wall -Wextra -Werror -I/path/to/frank-quest/src -Inative/scumm \
  tests/check_scumm_renderer_host.c native/scumm/engine_platform.c -o /tmp/scumm-renderer-test
/tmp/scumm-renderer-test
timeout 50 mpremote exec "PROFILE=1" + run tests/check_scumm_engine_device.py + reset
timeout 50 mpremote exec "PROFILE=2" + run tests/check_scumm_engine_device.py + reset
```

The renderer check compares every pixel against an independent sampling formula,
checks zoom switches, borders and clipped cursors using memory canaries. The game
check injects Escape and a mouse click, switches zoom twice and requires a clean
exit. It tests startup scenes, not complete playthroughs. MI1's SCUMM Bar scene
and German verb interface were visually checked at 480×300; its 27-second run
made 984 screen updates at 200 MHz. Screen updates are not a game-speed benchmark.
MI2 passed the same 27-second check with 1004 screen updates; its German
campfire opening scene was visually checked at 480×300. Both transferred
MI2 files (about 9.1 MB total) matched their source SHA256 hashes. The actual
device menu was checked with both games present and scripted navigation to MI1.

Optional `CAPTURE_PATH` writes a final 480×480 framebuffer (big-endian RGB565)
for visual inspection. Remove diagnostic captures afterward. Tests enable an
8-second watchdog, so reset after running, including if a failure skipped `+ reset`.

## Focused runtime probes

`scummprobe.mpy` remains a separate diagnostic for the original BOMP decoder,
real polymorphic MemoryReadStream, mutable globals/pointers, and a fixed 128 KiB
arena across 401 forced Python GC callbacks. It checks allocation, resizing,
fragmentation, exhaustion, callback failure and subsequent fresh sessions.

`tests/check_scumm_runtime_device.py` exercises the original buffered SD stream,
including large reads, relative seeking, EOF and cleanup. It creates/removes a
synthetic 32 KiB fixture. `prepare_fs.py` fixes an upstream bug: direct reads must
update `_bufStart`, otherwise `pos()` and SEEK_CUR use a stale offset.

Keep Python-owned arenas/callbacks live during native calls; native I/O buffer
views must not escape callbacks. Close files/native sessions in Python finally
blocks: Python exceptions cannot unwind C++ destructors. `audit.py` is only a
constructor dependency audit; use `build_engine.py` for the runnable engine.

`tests/check_scumm_slots_device.py` exercises the shared menu and real native
save/load in an isolated temporary directory. It never overwrites user slots.
