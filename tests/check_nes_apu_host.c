// Host check for native/nes/presto_apu.h (2A03 APU).
// gcc -O2 -std=gnu11 -o /tmp/apu tests/check_nes_apu_host.c && /tmp/apu
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Minimal stand-ins for the InfoNES symbols the APU uses.
int PPU_Scanline;
uint8_t memory[0x10000];
static uint8_t K6502_Read(uint16_t addr) { return memory[addr]; }
#include "../native/nes/presto_apu.h"

static int failures;
#define CHECK(c, ...) do { if (!(c)) { printf("FAIL %s:%d ", __FILE__, __LINE__); printf(__VA_ARGS__); puts(""); failures++; } } while (0)

static int16_t pcm[AUDIO_SAMPLES * 120];

static void write(unsigned reg, unsigned value, int line) {
    PPU_Scanline = line;
    apu_queue(reg, value);
}
static void frames(int n) {
    for (int f = 0; f < n; f++) {
        apu_frame();
        memcpy(pcm + f * AUDIO_SAMPLES, apu_out, sizeof(apu_out));
    }
}
static double frequency(int n) {
    int crossings = 0;
    for (int i = 1; i < n; i++) crossings += (pcm[i - 1] < 0) != (pcm[i] < 0);
    // One NTSC frame is 1/60.0988 s.
    return crossings / 2.0 / (n / (double)AUDIO_SAMPLES / 60.0988);
}
static int peak(int from, int n) {
    int p = 0;
    for (int i = from; i < from + n; i++) p = abs(pcm[i]) > p ? abs(pcm[i]) : p;
    return p;
}

int main(void) {
    apu_reset();
    frames(2);
    CHECK(peak(0, 2 * AUDIO_SAMPLES) == 0, "reset is silent");

    // Pulse 1, 50% duty, constant volume 15, period 253: 1789773/16/254 = 440.4 Hz
    write(0x15, 0x0f, 244);
    write(0x00, 0xbf, 244);
    write(0x02, 253 & 0xff, 244);
    write(0x03, (253 >> 8) | (1 << 3), 244);   // length index 1 = 254 frames
    frames(60);
    double f = frequency(60 * AUDIO_SAMPLES);
    CHECK(f > 436 && f < 445, "pulse A4 at %.1f Hz", f);
    CHECK(peak(0, 60 * AUDIO_SAMPLES) > 3000, "pulse audible %d", peak(0, 60 * AUDIO_SAMPLES));

    // Disabling the channel through $4015 silences it (length counter cleared).
    write(0x15, 0x00, 244);
    frames(20);
    CHECK(peak(10 * AUDIO_SAMPLES, 10 * AUDIO_SAMPLES) < 50, "disabled pulse silent %d",
          peak(10 * AUDIO_SAMPLES, 10 * AUDIO_SAMPLES));

    // Length counter: index 3 = 2 half frames, then silence (no halt flag).
    write(0x15, 0x01, 244);
    write(0x00, 0x9f, 244);
    write(0x03, (253 >> 8) | (3 << 3), 244);
    frames(20);
    CHECK(peak(10 * AUDIO_SAMPLES, 10 * AUDIO_SAMPLES) < 50, "length counter ends the note");

    // Envelope decays: no constant volume, period 0 -> silent after ~16 quarters.
    write(0x00, 0x80, 244);
    write(0x03, (253 >> 8) | (1 << 3), 244);
    frames(2);
    int early = peak(0, AUDIO_SAMPLES);
    frames(30);
    CHECK(early > 2000 && peak(20 * AUDIO_SAMPLES, 10 * AUDIO_SAMPLES) < 50, "envelope decays %d", early);

    // Triangle, period 126: 1789773/32/127 = 440.4 Hz; needs linear counter.
    write(0x15, 0x04, 244);
    write(0x08, 0xff, 244);                 // control set, linear reload 127
    write(0x0a, 126, 244);
    write(0x0b, (1 << 3), 244);
    frames(60);
    f = frequency(60 * AUDIO_SAMPLES);
    CHECK(f > 436 && f < 445, "triangle A4 at %.1f Hz", f);

    // Noise changes its output; mode 1 (short) too.
    write(0x15, 0x08, 244);
    write(0x0c, 0x3f, 244);
    write(0x0e, 0x04, 244);
    write(0x0f, (1 << 3), 244);
    frames(4);
    int changes = 0;
    for (int i = 1; i < 4 * AUDIO_SAMPLES; i++) changes += pcm[i] != pcm[i - 1];
    CHECK(changes > 300, "noise changes %d", changes);

    // DMC plays a sample from CPU memory: alternating bits move the level.
    write(0x15, 0x00, 244);
    frames(30);
    for (int i = 0; i < 64; i++) memory[0xc000 + i] = 0xff;
    write(0x10, 0x0f, 244);                 // fastest rate, no loop
    write(0x11, 0x00, 244);
    write(0x12, 0x00, 244);                 // $C000
    write(0x13, 0x03, 244);                 // 49 bytes
    write(0x15, 0x10, 244);
    frames(2);
    CHECK(peak(0, 2 * AUDIO_SAMPLES) > 2000, "DMC ramp audible %d", peak(0, 2 * AUDIO_SAMPLES));
    CHECK(apu_d.level > 60, "DMC level rose to %d", apu_d.level);

    // A write later in the frame takes effect later: silence first.
    apu_reset();
    write(0x15, 0x01, 244);
    write(0x00, 0xbf, 244);
    write(0x02, 253, 244);
    write(0x03, 1 << 3, 120);               // half way through the frame
    frames(1);
    CHECK(peak(0, AUDIO_SAMPLES / 3) == 0, "silent before the write %d", peak(0, AUDIO_SAMPLES / 3));
    CHECK(peak(0, AUDIO_SAMPLES) > 3000, "sound after the write");

    // Sweep down to period < 8 mutes instead of producing ultrasound.
    apu_reset();
    write(0x15, 0x01, 244);
    write(0x00, 0xbf, 244);
    write(0x02, 5, 244);
    write(0x03, 1 << 3, 244);
    frames(3);
    CHECK(peak(AUDIO_SAMPLES, 2 * AUDIO_SAMPLES) < 50, "period < 8 is muted");

    // Mixer tables never wrap: loud triangle + noise + DMC stays positive
    // and monotonic (an int16 table turned SMB3's drum hits into clicks).
    apu_reset();
    for (int n = 1; n < 203; n++)
        CHECK(apu_tnd_mix[n] > apu_tnd_mix[n - 1], "tnd mix monotonic at %d (%d)", n, (int)apu_tnd_mix[n]);
    for (int n = 1; n < 31; n++)
        CHECK(apu_pulse_mix[n] > apu_pulse_mix[n - 1], "pulse mix monotonic at %d", n);

    puts(failures ? "FAILED" : "PASS NES APU");
    return failures != 0;
}
