// NES 2A03 APU for the Presto (original adapter code, after nesdev.org):
// two pulses with envelope/sweep, triangle, noise and DMC sample playback,
// mixed with the hardware's nonlinear DAC curves to mono 16-bit samples,
// exactly AUDIO_SAMPLES per frame. Register writes are queued with their
// scanline time and applied at that sample when the frame is rendered.
// No DMC IRQ, no 5-step frame timing. The APU state is not saved: a loaded
// state restarts it silent until the game writes its next notes.

#define AUDIO_SAMPLES 367                 // per 16639 us frame: 22056 Hz
#define AUDIO_RATE 22056
#define APU_FRAME_LINES 263               // InfoNES scanlines 0..262
#define APU_LINES APU_FRAME_LINES
// Real NTSC frame length. InfoNES runs 262 x 113 = 29606 cycles per frame;
// timing the APU with those would play every note ~0.6% (10 cents) flat.
#define APU_FRAME_CYCLES 29781
#define APU_VSYNC_LINE 243                // SCAN_VBLANK_START
#define APU_EVENTS 1024
// DMC sample bytes are fetched at render time; the adapter can supply the
// memory as it was mapped at that point of the frame (cycle 0..29780).
#ifndef APU_DMC_READ
#define APU_DMC_READ(addr, cycle) K6502_Read(addr)
#endif

static const uint8_t apu_length[32] = {10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14,
                                       12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30};
static const uint8_t apu_duty[4] = {0x02, 0x06, 0x1e, 0xf9};   // bit n = sequence step n
static const uint16_t apu_noise_period[16] = {4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380,
                                              508, 762, 1016, 2034, 4068};
static const uint16_t apu_dmc_period[16] = {428, 380, 340, 320, 286, 254, 226, 214, 190, 160,
                                            142, 128, 106, 84, 72, 54};

struct ApuEnvelope { uint8_t start, divider, decay, period, loop, constant; };
struct ApuPulse {
    struct ApuEnvelope env;
    uint8_t duty, step, length, enabled, sweep_on, sweep_period, sweep_neg, sweep_shift;
    uint8_t sweep_div, sweep_reload, ones;
    uint16_t period;
    int32_t timer;
};
struct ApuTriangle {
    uint8_t control, reload_value, linear, reload, length, enabled, step;
    uint16_t period;
    int32_t timer;
};
struct ApuNoise {
    struct ApuEnvelope env;
    uint8_t mode, length, enabled;
    uint16_t period, lfsr;
    int32_t timer;
};
struct ApuDmc {
    uint8_t loop, rate, level, buffer, buffered, shift, bits, silence;
    uint16_t start, length, address, remaining;
    int32_t timer;
};
struct ApuEvent { uint16_t time; uint8_t reg, value; };

struct ApuPulse apu_p[2];
struct ApuTriangle apu_t;
struct ApuNoise apu_n;
struct ApuDmc apu_d;
struct ApuEvent apu_events[APU_EVENTS];
unsigned apu_event_count;
// int32: loud triangle/noise/DMC mixes exceed 32767 (an int16 table wrapped
// them negative: a full-scale click on SMB3's drum hits).
int32_t apu_pulse_mix[31];
int32_t apu_tnd_mix[203];
// The console's output filters (nesdev): first-order high-passes at 90 Hz
// and 440 Hz (the 14 kHz low-pass lies above Nyquist). Without the 440 Hz
// stage DMC kicks and level jumps thump hard and eat the headroom.
int32_t apu_hp_in, apu_hp_out, apu_hp2_out;
#define APU_HP90 31949                    // Q15: 1 / (1 + 2 pi 90 / 22056)
#define APU_HP440 29127                   // Q15: 1 / (1 + 2 pi 440 / 22056)
int16_t apu_out[AUDIO_SAMPLES];

static void apu_tables(void) {
    // pulse: 95.52 / (8128/n + 100); tnd: 163.67 / (24329/n + 100). Full scale
    // 96000: after the output high-passes SMB3 peaks near 22000 of 32767.
    apu_pulse_mix[0] = apu_tnd_mix[0] = 0;
    for (int n = 1; n < 31; n++) apu_pulse_mix[n] = (int32_t)(96000.0f * 0.9552f / (81.28f / n + 1.0f));
    for (int n = 1; n < 203; n++) apu_tnd_mix[n] = (int32_t)(96000.0f * 1.6367f / (243.29f / n + 1.0f));
}

static void apu_reset(void) {
    memset(apu_p, 0, sizeof(apu_p));
    memset(&apu_t, 0, sizeof(apu_t));
    memset(&apu_n, 0, sizeof(apu_n));
    memset(&apu_d, 0, sizeof(apu_d));
    apu_p[0].ones = 1;                    // pulse 1 negates in ones' complement
    apu_n.lfsr = 1;
    apu_n.period = apu_noise_period[0];
    apu_d.bits = 8;
    apu_d.silence = 1;
    apu_event_count = 0;
    memset(apu_out, 0, sizeof(apu_out));
    apu_tables();
    // The idle triangle holds step 0 (level 15): start the DC blocker on that
    // level, otherwise every reset/state load begins with a thump.
    apu_hp_in = apu_tnd_mix[3 * 15];
    apu_hp_out = apu_hp2_out = 0;
}

// Called from the CPU write handlers ($4000-$4013, $4015, $4017).
static void apu_queue(unsigned reg, unsigned value) {
    if (apu_event_count >= APU_EVENTS) return;
    unsigned line = (PPU_Scanline + APU_FRAME_LINES - APU_VSYNC_LINE - 1) % APU_FRAME_LINES;
    struct ApuEvent *e = &apu_events[apu_event_count++];
    e->time = (uint16_t)(line * APU_FRAME_CYCLES / APU_FRAME_LINES);
    e->reg = (uint8_t)reg;
    e->value = (uint8_t)value;
}

static void apu_envelope_write(struct ApuEnvelope *e, unsigned v) {
    e->loop = (v >> 5) & 1;
    e->constant = (v >> 4) & 1;
    e->period = v & 15;
}
static unsigned apu_envelope_volume(const struct ApuEnvelope *e) {
    return e->constant ? e->period : e->decay;
}
static void apu_envelope_clock(struct ApuEnvelope *e) {
    if (e->start) {
        e->start = 0;
        e->decay = 15;
        e->divider = e->period;
    } else if (e->divider) {
        e->divider--;
    } else {
        e->divider = e->period;
        if (e->decay) e->decay--;
        else if (e->loop) e->decay = 15;
    }
}

static unsigned apu_sweep_target(const struct ApuPulse *p) {
    unsigned change = p->period >> p->sweep_shift;
    if (!p->sweep_neg) return p->period + change;
    return change + p->ones > p->period ? 0 : p->period - change - p->ones;
}
static int apu_pulse_muted(const struct ApuPulse *p) {
    return p->period < 8 || (!p->sweep_neg && apu_sweep_target(p) > 0x7ff);
}

static void apu_apply(unsigned reg, unsigned v) {
    if (reg < 8) {
        struct ApuPulse *p = &apu_p[reg >> 2];
        switch (reg & 3) {
        case 0: p->duty = v >> 6; apu_envelope_write(&p->env, v); break;
        case 1:
            p->sweep_on = v >> 7; p->sweep_period = (v >> 4) & 7;
            p->sweep_neg = (v >> 3) & 1; p->sweep_shift = v & 7; p->sweep_reload = 1;
            break;
        case 2: p->period = (p->period & 0x700) | v; break;
        case 3:
            p->period = (p->period & 0xff) | ((v & 7) << 8);
            if (p->enabled) p->length = apu_length[v >> 3];
            p->step = 0;
            p->env.start = 1;
            break;
        }
        return;
    }
    switch (reg) {
    case 0x08: apu_t.control = v >> 7; apu_t.reload_value = v & 0x7f; break;
    case 0x0a: apu_t.period = (apu_t.period & 0x700) | v; break;
    case 0x0b:
        apu_t.period = (apu_t.period & 0xff) | ((v & 7) << 8);
        if (apu_t.enabled) apu_t.length = apu_length[v >> 3];
        apu_t.reload = 1;
        break;
    case 0x0c: apu_envelope_write(&apu_n.env, v); break;
    case 0x0e: apu_n.mode = v >> 7; apu_n.period = apu_noise_period[v & 15]; break;
    case 0x0f:
        if (apu_n.enabled) apu_n.length = apu_length[v >> 3];
        apu_n.env.start = 1;
        break;
    case 0x10: apu_d.loop = (v >> 6) & 1; apu_d.rate = v & 15; break;
    case 0x11: apu_d.level = v & 0x7f; break;
    case 0x12: apu_d.start = 0xc000 + v * 64; break;
    case 0x13: apu_d.length = v * 16 + 1; break;
    case 0x15:
        apu_p[0].enabled = v & 1; apu_p[1].enabled = (v >> 1) & 1;
        apu_t.enabled = (v >> 2) & 1; apu_n.enabled = (v >> 3) & 1;
        if (!apu_p[0].enabled) apu_p[0].length = 0;
        if (!apu_p[1].enabled) apu_p[1].length = 0;
        if (!apu_t.enabled) apu_t.length = 0;
        if (!apu_n.enabled) apu_n.length = 0;
        if (!(v & 0x10)) apu_d.remaining = 0;
        else if (!apu_d.remaining) { apu_d.address = apu_d.start; apu_d.remaining = apu_d.length; }
        break;
    }
}

static void apu_quarter(void) {
    apu_envelope_clock(&apu_p[0].env);
    apu_envelope_clock(&apu_p[1].env);
    apu_envelope_clock(&apu_n.env);
    if (apu_t.reload) apu_t.linear = apu_t.reload_value;
    else if (apu_t.linear) apu_t.linear--;
    if (!apu_t.control) apu_t.reload = 0;
}
static void apu_half(void) {
    for (int i = 0; i < 2; i++) {
        struct ApuPulse *p = &apu_p[i];
        if (!p->env.loop && p->length) p->length--;
        if (!p->sweep_div && p->sweep_on && p->sweep_shift && !apu_pulse_muted(p))
            p->period = apu_sweep_target(p);
        if (!p->sweep_div || p->sweep_reload) { p->sweep_div = p->sweep_period; p->sweep_reload = 0; }
        else p->sweep_div--;
    }
    if (!apu_t.control && apu_t.length) apu_t.length--;
    if (!apu_n.env.loop && apu_n.length) apu_n.length--;
}

// Each channel advances n CPU cycles and returns its level summed over them
// (box filter against aliasing of fast square waves).
static int apu_pulse_run(struct ApuPulse *p, int n) {
    int period = (p->period + 1) * 2;
    int level = p->length && !apu_pulse_muted(p) ? apu_envelope_volume(&p->env) : 0;
    int sum = 0;
    while (n) {
        if (p->timer <= 0) p->timer = period;
        int step = p->timer < n ? p->timer : n;
        if ((apu_duty[p->duty] >> p->step) & 1) sum += level * step;
        p->timer -= step;
        n -= step;
        if (!p->timer) p->step = (p->step + 1) & 7;
    }
    return sum;
}
static int apu_triangle_value(unsigned step) { return step < 16 ? 15 - step : step - 16; }
static int apu_triangle_run(int n) {
    // Ultrasonic periods hold the sequencer (as on hardware, they are inaudible).
    int active = apu_t.length && apu_t.linear && apu_t.period >= 2;
    int period = apu_t.period + 1, sum = 0;
    while (n) {
        if (!active) return sum + apu_triangle_value(apu_t.step) * n;
        if (apu_t.timer <= 0) apu_t.timer = period;
        int step = apu_t.timer < n ? apu_t.timer : n;
        sum += apu_triangle_value(apu_t.step) * step;
        apu_t.timer -= step;
        n -= step;
        if (!apu_t.timer) apu_t.step = (apu_t.step + 1) & 31;
    }
    return sum;
}
static int apu_noise_run(int n) {
    int level = apu_n.length ? apu_envelope_volume(&apu_n.env) : 0, sum = 0;
    while (n) {
        if (apu_n.timer <= 0) apu_n.timer = apu_n.period;
        int step = apu_n.timer < n ? apu_n.timer : n;
        if (!(apu_n.lfsr & 1)) sum += level * step;
        apu_n.timer -= step;
        n -= step;
        if (!apu_n.timer) {
            unsigned bit = (apu_n.lfsr ^ (apu_n.lfsr >> (apu_n.mode ? 6 : 1))) & 1;
            apu_n.lfsr = (apu_n.lfsr >> 1) | (bit << 14);
        }
    }
    return sum;
}
static int apu_dmc_run(int n, unsigned cycle) {
    int sum = 0;
    while (n) {
        if (!apu_d.buffered && apu_d.remaining) {
            apu_d.buffer = APU_DMC_READ(apu_d.address, cycle);
            apu_d.buffered = 1;
            apu_d.address = apu_d.address == 0xffff ? 0x8000 : apu_d.address + 1;
            if (!--apu_d.remaining && apu_d.loop) {
                apu_d.address = apu_d.start;
                apu_d.remaining = apu_d.length;
            }
        }
        if (apu_d.timer <= 0) apu_d.timer = apu_dmc_period[apu_d.rate];
        int step = apu_d.timer < n ? apu_d.timer : n;
        sum += apu_d.level * step;
        apu_d.timer -= step;
        n -= step;
        if (apu_d.timer) continue;
        if (!apu_d.silence) {
            if (apu_d.shift & 1) { if (apu_d.level <= 125) apu_d.level += 2; }
            else if (apu_d.level >= 2) apu_d.level -= 2;
            apu_d.shift >>= 1;
        }
        if (!--apu_d.bits) {
            apu_d.bits = 8;
            apu_d.silence = !apu_d.buffered;
            if (apu_d.buffered) { apu_d.shift = apu_d.buffer; apu_d.buffered = 0; }
        }
    }
    return sum;
}

// Renders one frame (vsync to vsync) into apu_out.
static void apu_frame(void) {
    unsigned e = 0;
    // Frame counter: four quarter-frame clocks (240 Hz), two of them half
    // frames. The 5-step mode (192 Hz) is approximated with the same rate.
    int next_quarter = 0, quarter = 0;
    uint32_t pos = 0;                     // Q8 CPU cycles
    const uint32_t per = ((uint32_t)APU_FRAME_CYCLES << 8) / AUDIO_SAMPLES;
    for (int i = 0; i < AUDIO_SAMPLES; i++) {
        uint32_t end = pos + per;
        unsigned t_end = end >> 8;
        while (e < apu_event_count && apu_events[e].time < t_end) {
            apu_apply(apu_events[e].reg, apu_events[e].value);
            e++;
        }
        if (i == next_quarter && quarter < 4) {
            apu_quarter();
            if (quarter & 1) apu_half();
            quarter++;
            next_quarter = quarter * AUDIO_SAMPLES / 4;
        }
        int n = (int)(t_end - (pos >> 8));
        pos = end;
        if (n <= 0) { apu_out[i] = i ? apu_out[i - 1] : 0; continue; }
        int p1 = apu_pulse_run(&apu_p[0], n), p2 = apu_pulse_run(&apu_p[1], n);
        int tr = apu_triangle_run(n), no = apu_noise_run(n), dm = apu_dmc_run(n, t_end);
        int pulse = (p1 + p2 + n / 2) / n;
        int tnd = (3 * tr + 2 * no + dm + n / 2) / n;
        if (pulse > 30) pulse = 30;
        if (tnd > 202) tnd = 202;
        int x = apu_pulse_mix[pulse] + apu_tnd_mix[tnd];
        // y = a (y' + x - x'), twice (division rounds toward zero; a shift
        // would floor negative values and leave a constant offset)
        int32_t h1 = (int32_t)(((int64_t)(apu_hp_out + x - apu_hp_in) * APU_HP90) / 32768);
        apu_hp2_out = (int32_t)(((int64_t)(apu_hp2_out + h1 - apu_hp_out) * APU_HP440) / 32768);
        apu_hp_out = h1;
        apu_hp_in = x;
        int y = apu_hp2_out;
        apu_out[i] = (int16_t)(y > 32767 ? 32767 : y < -32767 ? -32767 : y);
    }
    while (e < apu_event_count) {         // writes after the last sample edge
        apu_apply(apu_events[e].reg, apu_events[e].value);
        e++;
    }
    apu_event_count = 0;
}
