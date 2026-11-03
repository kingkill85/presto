// Feasibility test: a native module (C, no new firmware) that writes straight
// into the Presto's framebuffer (memoryview(display), RGB565, 480x480).

#include "py/dynruntime.h"

#define W 480
#define H 480
#define GB_W 160
#define GB_H 144

// fill(fb, t): a moving colour pattern over the whole screen
static mp_obj_t fill(mp_obj_t fb_in, mp_obj_t t_in) {
    mp_buffer_info_t fb;
    mp_get_buffer_raise(fb_in, &fb, MP_BUFFER_WRITE);
    if (fb.len < W * H * 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer too small"));
    }
    uint16_t *p = fb.buf;
    int t = mp_obj_get_int(t_in);
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            int r = ((x + t) >> 4) & 31, g = ((y * 2 + t) >> 3) & 63, b = ((x + y - t) >> 4) & 31;
            *p++ = (r << 11) | (g << 5) | b;
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(fill_obj, fill);

// blit3(fb, src): a 160x144 RGB565 picture, three times as big, centred
// at the top (480x432), like the Game Boy screen will be
static mp_obj_t blit3(mp_obj_t fb_in, mp_obj_t src_in) {
    mp_buffer_info_t fb, src;
    mp_get_buffer_raise(fb_in, &fb, MP_BUFFER_WRITE);
    mp_get_buffer_raise(src_in, &src, MP_BUFFER_READ);
    if (fb.len < W * H * 2 || src.len < GB_W * GB_H * 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("buffer too small"));
    }
    const uint16_t *s = src.buf;
    uint16_t *d = fb.buf;
    for (int y = 0; y < GB_H; y++) {
        uint16_t *row = d + y * 3 * W;
        for (int x = 0; x < GB_W; x++) {
            uint16_t c = s[y * GB_W + x];
            row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = c;
        }
        for (int i = 1; i < 3; i++) {  // the same row twice more
            uint16_t *to = row + i * W;
            for (int x = 0; x < W; x++) {
                to[x] = row[x];
            }
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(blit3_obj, blit3);

// blit15(fb, src): the 160x144 picture 1.5 times as big (240x216) on the
// half resolution screen (240x240, every pixel doubled by the display)
static mp_obj_t blit15(mp_obj_t fb_in, mp_obj_t src_in) {
    mp_buffer_info_t fb, src;
    mp_get_buffer_raise(fb_in, &fb, MP_BUFFER_WRITE);
    mp_get_buffer_raise(src_in, &src, MP_BUFFER_READ);
    if (fb.len < 240 * 240 * 2 || src.len < GB_W * GB_H * 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("buffer too small"));
    }
    const uint16_t *s = src.buf;
    uint16_t *d = fb.buf;
    for (int y = 0; y < 216; y++) {
        const uint16_t *line = s + (y * 2 / 3) * GB_W;
        uint16_t *to = d + y * 240;
        for (int x = 0; x < 240; x++) {
            to[x] = line[x * 2 / 3];
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(blit15_obj, blit15);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_fill, MP_OBJ_FROM_PTR(&fill_obj));
    mp_store_global(MP_QSTR_blit3, MP_OBJ_FROM_PTR(&blit3_obj));
    mp_store_global(MP_QSTR_blit15, MP_OBJ_FROM_PTR(&blit15_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
