// Host check for native/sms/presto_psg.h (SN76489).
// gcc -O2 -std=gnu11 -o /tmp/psg tests/check_sms_psg_host.c && /tmp/psg
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../native/sms/presto_psg.h"

static int failures;
#define CHECK(c, ...) do { if (!(c)) { printf("FAIL %s:%d ", __FILE__, __LINE__); printf(__VA_ARGS__); puts(""); failures++; } } while (0)

static unsigned now;
static int16_t pcm[AUDIO_SAMPLES * 60];

// Runs n frames like TotalSMS: end_frame at each frame end, then audio().
static void frames(int n) {
    for (int f = 0; f < n; f++) {
        now += PSG_FRAME_CYCLES;
        psg_end_frame(&presto_psg, now);
        psg_take(pcm + f * AUDIO_SAMPLES);
    }
}

static void tone(int channel, int period, int attenuation) {
    psg_write_io(&presto_psg, 0x80 | channel << 5 | (period & 15), now);
    psg_write_io(&presto_psg, period >> 4, now);
    psg_write_io(&presto_psg, 0x90 | channel << 5 | attenuation, now);
}

static double frequency(int n) {
    int crossings = 0;
    for (int i = 1; i < n; i++) crossings += (pcm[i - 1] < 0) != (pcm[i] < 0);
    return crossings / 2.0 / (n / (double)AUDIO_RATE);
}

static int peak(int n) {
    int p = 0;
    for (int i = 0; i < n; i++) p = abs(pcm[i]) > p ? abs(pcm[i]) : p;
    return p;
}

int main(void) {
    psg_reset(&presto_psg, Sn76489LfsrTappedBit_SMS, Sn76489LfsrFeedBit_SMS);
    frames(2);
    CHECK(peak(2 * AUDIO_SAMPLES) == 0, "reset is silent");

    // 3579545 / (32 * 254) = 440.4 Hz
    tone(0, 254, 0);
    frames(60);
    double f = frequency(60 * AUDIO_SAMPLES);
    CHECK(f > 436 && f < 445, "A4 tone at %.1f Hz", f);
    CHECK(peak(60 * AUDIO_SAMPLES) > 7000, "full volume peak %d", peak(60 * AUDIO_SAMPLES));

    tone(0, 254, 6);                     // -12 dB
    frames(10);
    int quieter = peak(10 * AUDIO_SAMPLES);
    CHECK(quieter > 1800 && quieter < 2300, "attenuation 6 peak %d", quieter);

    // Period 0/1: constant output, PCM through volume writes still audible.
    tone(0, 0, 0);
    frames(2);
    CHECK(pcm[AUDIO_SAMPLES] > 7000 && pcm[2 * AUDIO_SAMPLES - 1] > 7000, "period 0 is high");

    // Game Gear routing off for all channels mutes them.
    psg_gg_write_io(&presto_psg, 0x00, now);
    frames(2);
    CHECK(peak(2 * AUDIO_SAMPLES) == 0, "GG routing mutes");
    psg_gg_write_io(&presto_psg, 0xff, now);
    psg_write_io(&presto_psg, 0x9f, now);   // channel 0 off

    // White noise varies; noise register write keeps sample count exact.
    psg_write_io(&presto_psg, 0xe4, now);
    psg_write_io(&presto_psg, 0xf0, now);
    frames(4);
    int changes = 0;
    for (int i = 1; i < 4 * AUDIO_SAMPLES; i++) changes += pcm[i] != pcm[i - 1];
    CHECK(changes > 200, "white noise changes %d", changes);

    // Mid-frame writes land in time: tone starts half way through the frame.
    psg_write_io(&presto_psg, 0xff, now);
    tone(1, 254, 15);
    now += PSG_FRAME_CYCLES / 2;
    psg_write_io(&presto_psg, 0xb0, now);   // channel 1 to full volume
    now += PSG_FRAME_CYCLES / 2;
    psg_end_frame(&presto_psg, now);
    psg_take(pcm);
    CHECK(peak(AUDIO_SAMPLES / 2 - 2) == 0, "silent before the write");
    CHECK(peak(AUDIO_SAMPLES) > 7000, "sound after the write");

    // Exactly one frame of samples per frame over a long run (no drift).
    unsigned before = psg_write_pos;
    frames(60);
    unsigned made = psg_write_pos - before;
    CHECK(made >= 60 * AUDIO_SAMPLES - 1 && made <= 60 * AUDIO_SAMPLES + 1, "samples per second %u", made);

    // State round trip; an old silent-core state (zeros) restarts silent.
    unsigned char state[512];
    CHECK(psg_save_state(&presto_psg, state, sizeof(state), 0) == 0, "save");
    struct Sn76489 saved = presto_psg;
    psg_reset(&presto_psg, Sn76489LfsrTappedBit_SMS, Sn76489LfsrFeedBit_SMS);
    psg_load_state(&presto_psg, state, sizeof(state), 0);
    CHECK(!memcmp(&saved, &presto_psg, sizeof(saved)), "state round trip");
    memset(state, 0, sizeof(state));
    psg_load_state(&presto_psg, state, sizeof(state), 0);
    frames(2);
    CHECK(peak(2 * AUDIO_SAMPLES) == 0, "old state is silent");
    tone(2, 254, 0);
    frames(2);
    CHECK(peak(2 * AUDIO_SAMPLES) > 7000, "sound after old state");

    // Timestamp rebasing (scheduler timeout) keeps rendering continuous.
    psg_update_timestamp(&presto_psg, -(int)now);
    now = 0;
    before = psg_write_pos;
    frames(2);
    CHECK(psg_write_pos - before >= 2 * AUDIO_SAMPLES - 1, "rebased timestamps");

    puts(failures ? "FAILED" : "PASS SMS PSG");
    return failures != 0;
}
