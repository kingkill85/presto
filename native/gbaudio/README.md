# Game Boy mixed audio

The normal Retro launcher selects `gbaudiocore` for monochrome Game Boy ROMs
and `gbccore` for Game Boy Color, including CGB-flagged `.gb` files.
MiniGB APU mixes both pulse channels, wave and noise to mono PWM on Presto's
GPIO43 piezo. Sega (own PSG in native/sms), NES (own APU in native/nes) and SCUMM have their own audio. No extra hardware or firmware upgrade is needed.

Build with MicroPython v1.26.0:

```sh
make -C native/gbaudio MPY_DIR=/absolute/path/to/micropython MKDIR=mkdir RM=rm
timeout 20 mpremote fs cp native/gbaudio/gbaudiocore.mpy :/lib/gbaudiocore.mpy
timeout 20 mpremote fs cp device/lib/retro_audio.py device/lib/retro.py device/lib/retro_roms.py device/lib/game_storage.py device/lib/game_ui.py :/lib/
```

SELECT+START opens the game menu. The `Ton` row cycles through off, 30%, 60%
(default) and 100%, stored per ROM in `/sd/games.json`. All pause-menu entries fit on one page; changing volume preserves selection.
Other engines retain their existing menu.
Audio stops before menus, state operations, battery saves, pad disconnects,
clock changes and exit. Reconnection recreates output at the emulation clock.
Silent volume still advances the APU so re-enabling sound preserves timing.

`presto-gb-audio-v2` and `presto-gbc-audio-v2` states contain the CPU, APU and cartridge RAM. They clear
host pointers and rebind CPU callbacks on load. The slot layer validates ROM,
core, exact size and checksum; the native loader checks APU invariants before
mutation. Old `presto-gb-v1` and `presto-gbc-v1` quick states are incompatible and rejected;
battery `.sav` files remain compatible. The old silent `gbcore` build and its
240px diagnostic API are retained.

## Output and limitations

`retro_audio.Audio` primes two caller-owned buffers before playback. Two DMA
channels are claimed through firmware. A prepared buffer is linked from the
playing buffer; the last buffer always has chaining disabled. There is no
cyclic DMA loop, IRQ handler or retained stack pointer. If the producer stalls,
DMA exhausts the finite queue, holds its final duty and stops without reading
past either buffer. The next frame restarts playback and counts an underrun.
On pause both links are disabled before either channel is released, and GPIO43
is driven low. The PWM rate is recreated after CPU clock changes.

Sound register writes are frame-granular, not cycle-accurate. Nominal 22050 Hz
synthesis emits 369 samples/frame, played at 22039 Hz to approximate original
DMG speed. The piezo and PWM carrier limit fidelity; this is mixed game audio,
not a claim of exact sound-hardware reproduction.

## Hardware checks

```sh
timeout 20 mpremote fs cp tests/rom_fixtures.py :/lib/rom_fixtures.py
timeout 20 mpremote run tests/gb_audio_stream_device.py
timeout 25 mpremote run tests/gb_audio_runtime_device.py
timeout 20 mpremote reset
```

The original four-channel fixture contains no third-party ROM data. Its channels
produce distinct varying samples; routing off and zero volume produce silence.
The buffered output ran 180 frames in 2999 ms with zero underruns; a forced
100ms starvation stopped both channels exactly at buffer ends and recovered
with one counted underrun. Normal and exception cleanup restore GPIO and clock.
The earlier single-DMA prototype (`gb_audio_probe.py`) remains available for
comparison. Super Mario Land audio was audibly confirmed on actual hardware.

The integrated console test completed 600 frames in 11019 ms (including menu,
state I/O and simulated disconnect), with zero underruns. All five state slots
roundtripped; pause, disconnect and exception cleanup restored the normal CPU
clock and drove GPIO43 low. Super Mario Land completed 900 frames in 15955 ms
including loading and a menu/state pause, also with zero underruns. Host suite:
87 tests passed. These are hardware runs, not electrical waveform measurements.

MicroPython 1.26 `DMA.close()` only releases the channel claim. The output
explicitly aborts with `active(0)` before closing; omitting that abort caused
paused transfers to survive channel reuse during development. Both links are
disabled first so aborting cannot start a channel that has already been freed.
Linked control words are cached and menu/state garbage is collected before
resuming audio to reduce producer stalls.

GBC uses the same mixer/output, compiled with Walnut-CGB and its existing
optimization flags (`make -C native/gbc ...`). `tests/gbc_audio_device.py`
checks identical PCM at normal and double CPU speed, sound state roundtrips
and truncated-state rejection. The full GBC console fixture ran 600 frames
in 11755 ms including menu/state I/O and a simulated disconnect, with zero
underruns; all five audio-aware state slots passed. CGB-specific audio quirks
are not fully modeled by the shared MiniGB mixer.

GBC rendering is capped at 30 images/s while CPU and audio continue at the
original frame rate. Zelda DX produced 900 emulated frames with a menu/state
pause and 873 varying audio blocks, with zero underruns in this mode (four
underruns occurred with unrestricted rendering). The shared output rate was
measured independently using 110700 samples: 5023246 us, about 22037 Hz versus
22039 Hz requested. Test tones measured 439.59/329.09 Hz against expected
439.84/329.33 Hz. These checks exclude a global output-rate multiplier, but
are not a reference comparison of every game's music driver.

### Music-tempo correction

Earlier sample-rate and test-tone measurements did not validate game tempo.
A CPU-cycle trace identified discarded scanline overshoot in both emulator
cores. Before correction, Super Mario Land advanced about 79250 emulated
clocks per host frame instead of 70224 (about 12.9% excess); Zelda DX's traced
sequence averaged about 75230 (about 7.1% excess). Preserve the remainder at
mode-2 entry, in Peanut-GB and all three Walnut execution paths.

After correction both traces average 70224 clocks/frame. Mario's regular
channel-1 note intervals change from mostly 13 frames to mostly 15; a PyBoy
reference with the same user-provided ROM confirms the 15-frame intervals
(including a run of 23 exactly matching consecutive intervals). No game data
or recordings are committed. Playback sample rate and oscillator pitch are
unchanged. This fixes a CPU/LCD timing error, not a global audio resampling
factor. The new original-ROM regression fails against both old headers and
passes against the corrected ones, including CGB double speed.
