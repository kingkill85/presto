# RP2350 audio FIFO helper

Build with MicroPython v1.26.0 using `make MPY_DIR=/path/to/micropython`,
then install `audiofifo.mpy` in `/lib` with `retro_audio.py`.

GB/GBC audio buffers live in PSRAM. Direct DMA reads can stall display DMA.
This helper cleans each buffer's CPU cache lines and streams its words through
XIP_AUX, which the audio DMA reads at the existing PWM sample rate. SCUMM's
SRAM buffers continue to use direct DMA.

The streamer holds one stream at a time, so the next block can only be
appended once the previous one has drained. `retro_audio` therefore queues
two-frame blocks (`BLOCK_FRAMES`): with one-frame blocks every frame slower
than 16.7 ms underran (Zelda DX, drawn GBC frames ~18.5 ms: 744 underruns in
70 s, now 28 with full 59.7 fps).

The Python owner reserves an idle, empty streamer, waits for its counter to
reach zero, and configures finite self-chained DMA transfers. `queue` appends
without discarding the previous stream's final FIFO samples, then links the
previous channel to the next. A short interrupt-masked section resolves a
completion racing the handoff. It does not hold interrupts off while waiting
for FIFO data. Pausing aborts both owned DMA channels before draining the
streamer and restoring its address. No display channels are modified.

Hardware check: `timeout 30 mpremote run tests/check_audio_fifo_device.py`.
It compares every byte over 20 pairs of streams, including deliberately
starved handoffs, with silent PWM pacing and an SRAM destination.

Register definitions and cache operations follow Raspberry Pi's official
[RP2350 SDK](https://github.com/raspberrypi/pico-sdk/tree/master/src/rp2350)
and [cache maintenance implementation](https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2_common/hardware_xip_cache/xip_cache.c).
This is original adapter code; no upstream source is vendored.
