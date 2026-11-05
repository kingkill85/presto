// Shared RGB565 framebuffer helpers. The Presto expects byte-swapped RGB565.
#pragma once
#include "py/dynruntime.h"
#include <stdint.h>
#include <stddef.h>

static inline uint16_t retro_pen(unsigned r, unsigned g, unsigned b) {
    uint16_t rgb = ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3);
    return __builtin_bswap16(rgb);
}
static inline uint16_t *retro_fb(mp_obj_t obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(obj, &b, MP_BUFFER_WRITE);
    if (b.len < 480 * 480 * 2 || ((uintptr_t)b.buf & 3)) {
        mp_raise_ValueError(MP_ERROR_TEXT("retro: framebuffer must be aligned 480x480 RGB565"));
    }
    return b.buf;
}
// Exactly 3x for 160px handhelds; caller provides the cached 240-word row.
// All three rows in one pass: four pixels become 12 (three 64-bit stores per
// row). pixels must be 4-byte aligned; row is unused.
static inline void retro_line3(uint16_t *fb, int y, const uint16_t *pixels, uint32_t *row) {
    uint64_t *r0 = (uint64_t *)(fb + (24 + y * 3) * 480);
    uint64_t *r1 = r0 + 120, *r2 = r1 + 120;
    const uint32_t *in = (const uint32_t *)pixels;
    for (int x = 0, out = 0; x < 80; x += 2, out += 3) {
        uint32_t ab = in[x], cd = in[x + 1];
        uint32_t a = ab & 0xffff, b = ab >> 16, c = cd & 0xffff, d = cd >> 16;
        uint64_t w0 = (a | (a << 16)) | ((uint64_t)(a | (b << 16)) << 32);
        uint64_t w1 = (b | (b << 16)) | ((uint64_t)(c | (c << 16)) << 32);
        uint64_t w2 = (c | (d << 16)) | ((uint64_t)(d | (d << 16)) << 32);
        r0[out] = w0; r0[out + 1] = w1; r0[out + 2] = w2;
        r1[out] = w0; r1[out + 1] = w1; r1[out + 2] = w2;
        r2[out] = w0; r2[out + 1] = w1; r2[out + 2] = w2;
    }
}

// 256px consoles: crop eight source pixels per side, then exactly 2x.
// Both output rows in one pass, two pixels per 64-bit store (row is unused).
static inline void retro_line2(uint16_t *fb, int y, int top, const uint16_t *pixels, uint32_t *row) {
    uint64_t *a = (uint64_t *)(fb + (top + y * 2) * 480);
    uint64_t *b = a + 120;
    const uint32_t *in = (const uint32_t *)(pixels + 8);
    for (int x = 0; x < 120; x++) {
        uint32_t two = in[x];
        uint32_t lo = two & 0xffff, hi = two >> 16;
        uint64_t w = (lo | (lo << 16)) | ((uint64_t)(hi | (hi << 16)) << 32);
        a[x] = w;
        b[x] = w;
    }
}
