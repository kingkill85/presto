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
static inline void retro_line3(uint16_t *fb, int y, const uint16_t *pixels, uint32_t *row) {
    for (int x = 0, out = 0; x < 160; x += 2, out += 3) {
        uint32_t a = pixels[x], b = pixels[x + 1];
        row[out] = a | (a << 16);
        row[out + 1] = a | (b << 16);
        row[out + 2] = b | (b << 16);
    }
    for (int dy = 0; dy < 3; dy++) {
        uint32_t *to = (uint32_t *)(fb + (24 + y * 3 + dy) * 480);
        for (int x = 0; x < 240; x++) to[x] = row[x];
    }
}

// 256px consoles: crop eight source pixels per side, then exactly 2x.
static inline void retro_line2(uint16_t *fb, int y, int top, const uint16_t *pixels, uint32_t *row) {
    for (int x = 0; x < 240; x++) {
        uint32_t c = pixels[x + 8];
        row[x] = c | (c << 16);
    }
    for (int dy = 0; dy < 2; dy++) {
        uint32_t *to = (uint32_t *)(fb + (top + y * 2 + dy) * 480);
        for (int x = 0; x < 240; x++) to[x] = row[x];
    }
}
