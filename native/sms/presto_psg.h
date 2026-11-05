// SN76489 PSG for the Presto: three square tones and LFSR noise, mixed to
// mono 16-bit samples, exactly AUDIO_SAMPLES per NTSC frame (22052 Hz).
// Implements the TotalSMS PSG API (vendor/sn76489.h); original adapter code.
// Register writes carry their CPU cycle, so output is rendered up to that
// cycle first (sample accurate). No pointers are kept in the saved state.
#include "vendor/sn76489.h"

#define PSG_FRAME_CYCLES (228 * 262)     // NTSC frame, CPU clock 3579545 Hz
#define AUDIO_SAMPLES 368                // 59736 cycles / 368 = 162.3 cycles
#define AUDIO_RATE 22052                 // 368 per 16688 us frame
#define PSG_RING 2048                    // power of two
#define PSG_MAGIC 0x50534731u            // "PSG1"
#define PSG_CHANNEL_MAX 8000             // four channels stay below 32767

struct Sn76489 {
    uint32_t magic;
    uint16_t period[3];
    uint16_t counter[4];
    uint8_t volume[4];                   // attenuation, 15 = off
    uint8_t out[3];
    uint8_t noise;                       // bit 2 white, bits 0-1 rate
    uint8_t noise_flip;
    uint8_t latch;                       // latched channel*2 + volume flag
    uint8_t enable;                      // Game Gear routing, mono: L | R
    uint16_t lfsr;
    uint16_t tapped;
    uint8_t feed;
    uint8_t resync;                      // next write/frame rebases timing
    int64_t next;                        // Q16 cycle at which the next sample ends
};

struct Sn76489 presto_psg;
int16_t psg_ring[PSG_RING];
unsigned psg_write_pos, psg_read_pos;
int16_t psg_last;                        // consumer: last sample played
int16_t psg_prev;                        // producer: last sample rendered

// 2 dB per attenuation step: 8000 * 10^(-i/10), 15 is silence.
const int16_t psg_amp[16] = {8000, 6355, 5048, 4009, 3185, 2530, 2009, 1596,
                             1268, 1007, 800, 635, 505, 401, 319, 0};
#define PSG_CYCLES_Q16 (((int64_t)PSG_FRAME_CYCLES << 16) / AUDIO_SAMPLES)

static int psg_tone(struct Sn76489 *p, int c, int n) {
    unsigned period = p->period[c];
    if (period <= 1) return n;           // Sega PSG: constant high (PCM via volume)
    unsigned count = p->counter[c] ? p->counter[c] : period;
    int out = p->out[c], high = 0;
    while (n) {
        int step = count < (unsigned)n ? (int)count : n;
        if (out) high += step;
        count -= step;
        n -= step;
        if (!count) { count = period; out ^= 1; }
    }
    p->counter[c] = count;
    p->out[c] = out;
    return high;
}

static int psg_noise(struct Sn76489 *p, int n) {
    unsigned rate = p->noise & 3;
    unsigned reload = rate == 3 ? p->period[2] : 0x10u << rate;
    if (!reload) reload = 1;
    unsigned count = p->counter[3] ? p->counter[3] : reload;
    int high = 0;
    while (n) {
        int step = count < (unsigned)n ? (int)count : n;
        if (p->lfsr & 1) high += step;
        count -= step;
        n -= step;
        if (!count) {
            count = reload;
            p->noise_flip ^= 1;
            if (p->noise_flip) {         // the LFSR shifts on the rising edge
                unsigned bit;
                if (p->noise & 4) {       // parity without a libgcc call
                    bit = p->lfsr & p->tapped;
                    bit ^= bit >> 8; bit ^= bit >> 4; bit ^= bit >> 2; bit ^= bit >> 1;
                    bit &= 1;
                } else bit = p->lfsr & 1;
                p->lfsr = (p->lfsr >> 1) | (bit << p->feed);
            }
        }
    }
    p->counter[3] = count;
    return high;
}

static void psg_sample(struct Sn76489 *p, int n) {
    int mix = 0;
    for (int c = 0; c < 3; c++) {
        int high = psg_tone(p, c, n);
        if (p->enable & (1 << c)) mix += psg_amp[p->volume[c]] * (2 * high - n) / n;
    }
    int high = psg_noise(p, n);
    if (p->enable & 8) mix += psg_amp[p->volume[3]] * (2 * high - n) / n;
    if (mix > 32767) mix = 32767;
    if (mix < -32767) mix = -32767;
    psg_prev = (int16_t)mix;
    psg_ring[psg_write_pos++ & (PSG_RING - 1)] = psg_prev;
    if (psg_write_pos - psg_read_pos > PSG_RING) psg_read_pos = psg_write_pos - PSG_RING;
}

static void psg_render(struct Sn76489 *p, unsigned time) {
    int64_t now = (int64_t)time << 16;
    // Far behind or more than two frames ahead: rebase instead of rendering.
    if (p->resync || now - p->next > ((int64_t)PSG_RING << 16) * 162 ||
        p->next - now > ((int64_t)PSG_FRAME_CYCLES << 17)) {
        p->resync = 0;                   // after a state from another build
        p->next = now + PSG_CYCLES_Q16;
        return;
    }
    while (p->next <= now) {
        int64_t start = p->next - PSG_CYCLES_Q16;
        // PSG counters tick every 16 CPU cycles: 10 or 11 per sample.
        int n = (int)((p->next >> 20) - (start >> 20));
        p->next += PSG_CYCLES_Q16;
        if (n > 0) psg_sample(p, n);
        else psg_ring[psg_write_pos++ & (PSG_RING - 1)] = psg_prev;
    }
}

Sn76489 *psg_init(double clock, double rate) { return &presto_psg; }
void psg_quit(Sn76489 *p) {}
void psg_reset(Sn76489 *p, unsigned tapped, unsigned feed) {
    memset(p, 0, sizeof(*p));
    p->magic = PSG_MAGIC;
    for (int c = 0; c < 4; c++) p->volume[c] = 15;
    p->enable = 0xff;
    p->lfsr = 0x8000;
    p->tapped = tapped;
    p->feed = feed;
    p->next = PSG_CYCLES_Q16;
    psg_write_pos = psg_read_pos = 0;
    psg_last = psg_prev = 0;
}
void psg_write_io(Sn76489 *p, unsigned value, unsigned time) {
    psg_render(p, time);
    if (value & 0x80) p->latch = (value >> 4) & 7;
    unsigned c = p->latch >> 1;
    if (p->latch & 1) {
        p->volume[c] = value & 15;
    } else if (c < 3) {
        p->period[c] = value & 0x80 ? (p->period[c] & 0x3f0) | (value & 15)
                                    : (p->period[c] & 15) | ((value & 0x3f) << 4);
    } else {
        p->noise = value & 7;
        p->lfsr = 0x8000;
    }
}
void psg_gg_write_io(Sn76489 *p, unsigned value, unsigned time) {
    psg_render(p, time);
    p->enable = (value | (value >> 4)) & 15;
}
void psg_set_channel_volume(Sn76489 *p, unsigned channel, float volume) {}
void psg_set_master_volume(Sn76489 *p, float volume) {}
void psg_update_timestamp(Sn76489 *p, int time) { p->next += (int64_t)time << 16; }
void psg_end_frame(Sn76489 *p, unsigned time) { psg_render(p, time); }
// Samples are kept in psg_ring for audio(); the upstream callback stays unused.
int psg_samples_avaliable(const Sn76489 *p) { return 0; }
int psg_read_samples(Sn76489 *p, short out[], int count) { return 0; }
void psg_clear_samples(Sn76489 *p) {}
unsigned psg_state_size(const Sn76489 *p, int include_blip) { return sizeof(struct Sn76489); }
int psg_save_state(const Sn76489 *p, void *data, unsigned size, int blip) {
    if (size < sizeof(*p)) return 1;
    memcpy(data, p, sizeof(*p));
    return 0;
}
int psg_load_state(Sn76489 *p, const void *data, unsigned size, int blip) {
    struct Sn76489 s;
    memcpy(&s, data, sizeof(s));
    // Older silent-core states hold no PSG: start silent instead of failing.
    if (size < sizeof(s) || s.magic != PSG_MAGIC || s.feed > 15 || (s.noise & ~7) ||
        s.latch > 7 || s.period[0] > 0x3ff || s.period[1] > 0x3ff || s.period[2] > 0x3ff) {
        psg_reset(p, p->tapped ? p->tapped : Sn76489LfsrTappedBit_SMS,
                  p->tapped ? p->feed : Sn76489LfsrFeedBit_SMS);
        p->resync = 1;
        return 0;
    }
    for (int c = 0; c < 4; c++) s.volume[c] &= 15;
    for (int c = 0; c < 3; c++) s.out[c] &= 1;
    s.noise_flip &= 1;
    if (!s.lfsr) s.lfsr = 0x8000;
    *p = s;
    psg_write_pos = psg_read_pos = 0;
    return 0;
}

// Exactly AUDIO_SAMPLES per call: pad with the last sample after a short
// frame, drop the oldest beyond one spare frame (bounded latency).
static void psg_take(int16_t *out) {
    unsigned have = psg_write_pos - psg_read_pos;
    if (have > 2 * AUDIO_SAMPLES) psg_read_pos = psg_write_pos - AUDIO_SAMPLES;
    for (int i = 0; i < AUDIO_SAMPLES; i++) {
        if (psg_read_pos != psg_write_pos) psg_last = psg_ring[psg_read_pos++ & (PSG_RING - 1)];
        out[i] = psg_last;
    }
}
