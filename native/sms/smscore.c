// TotalSMS, shared Game Gear / Master System adapter with PSG audio.
#include "../common/mpy_alloc.h"
#include "../common/retro_fb.h"
#define sms_static_assert _Static_assert
#define SMS_PRESTO_SCANLINE(sms, y) retro_sms_line(y)
static void retro_sms_line(int y);
#define SMS_SINGLE_FILE 1
#define SMS_PIXEL_WIDTH 16
#include "presto_psg.h"
#include "vendor/sms_single.c"

struct SMS_Core sega;
uint16_t *sega_pixels;
uint16_t *sega_framebuffer;
unsigned sega_scale;

int sega_initialized;

static uint32_t colour(void *user, uint8_t r, uint8_t g, uint8_t b) {
    unsigned factor = SMS_is_system_type_gg(&sega) ? 17 : 85;
    return retro_pen(r * factor, g * factor, b * factor);
}
static mp_obj_t init(size_t n, const mp_obj_t *args) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(args[0], &b, MP_BUFFER_READ);
    // The upstream header lookup probes up to 0x7fff; validate before calling.
    if (b.len < 32768 || b.len > 4 * 1024 * 1024 || (b.len & (b.len - 1))) {
        mp_raise_ValueError(MP_ERROR_TEXT("Sega: ROM must be 32K-4M, power of two"));
    }
    if (sega_initialized) SMS_quit(&sega);
    memset(&sega, 0, sizeof(sega));
    if (!SMS_init(&sega)) mp_raise_ValueError(MP_ERROR_TEXT("Sega: init failed"));
    sega_initialized = 1;
    int system = n == 2 && mp_obj_is_true(args[1]) ? SMS_System_GG : SMS_System_SMS;
    if (!SMS_loadromEx(&sega, b.buf, b.len, system, SMS_Region_NTSC, SMS_Console_EXPORT)) {
        mp_raise_ValueError(MP_ERROR_TEXT("Sega: unrecognized ROM header"));
    }
    SMS_set_colour_callback(&sega, colour);
    SMS_skip_audio(&sega, true);
    return mp_obj_new_int(sizeof(sega.cart_ram.ram));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(init_obj, 1, 2, init);
static mp_obj_t set_ram(mp_obj_t obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(obj, &b, MP_BUFFER_READ);
    if (!SMS_loadsave(&sega, b.buf, b.len)) mp_raise_ValueError(MP_ERROR_TEXT("Sega: save size"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(set_ram_obj, set_ram);
static mp_obj_t get_ram(void) {
    return mp_obj_new_bytearray_by_ref(sizeof(sega.cart_ram.ram), sega.cart_ram.ram);
}
static MP_DEFINE_CONST_FUN_OBJ_0(get_ram_obj, get_ram);
static mp_obj_t save_needed(void) {
    return SMS_used_sram(&sega) && SMS_is_sram_dirty(&sega, false) ? mp_const_true : mp_const_false;
}
static MP_DEFINE_CONST_FUN_OBJ_0(save_needed_obj, save_needed);
static mp_obj_t palette(size_t n, const mp_obj_t *args) { return mp_const_none; }
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(palette_obj, 4, 4, palette);
static mp_obj_t frame(size_t n, const mp_obj_t *args) {
    sega_framebuffer = retro_fb(args[0]);
    sega_scale = mp_obj_get_int(args[5]) == 2 ? 2 : 1;
    unsigned held = mp_obj_get_int(args[1]);
    unsigned keys = ((held & 64) ? SMS_Button_JOY1_UP : 0) |
        ((held & 128) ? SMS_Button_JOY1_DOWN : 0) |
        ((held & 32) ? SMS_Button_JOY1_LEFT : 0) |
        ((held & 16) ? SMS_Button_JOY1_RIGHT : 0) |
        ((held & 1) ? SMS_Button_JOY1_A : 0) |
        ((held & 2) ? SMS_Button_JOY1_B : 0) |
        ((held & 8) ? SMS_Button_PAUSE : 0);
    SMS_set_buttons(&sega, ~keys & 0x3fff, false);
    SMS_set_buttons(&sega, keys, true);
    bool draw = mp_obj_is_true(args[4]);
    SMS_skip_frame(&sega, !draw);
    uint16_t scanline[256] __attribute__((aligned(8)));  // read as words by retro_line2
    sega_pixels = scanline;
    SMS_set_pixels(&sega, scanline, 0, 16);
    SMS_run(&sega, SMS_RunEndFrame);
    SMS_set_pixels(&sega, NULL, 0, 16);
    sega_pixels = NULL;

    return mp_const_none;
}
static void retro_sms_line(int y) {
    uint32_t sega_line[240];
    if (SMS_is_system_type_gg(&sega)) {
        if (y >= 24 && y < 168) {
            if (sega_scale == 2) retro_line3(sega_framebuffer, y - 24, sega_pixels + 48, sega_line);
            else {
                uint32_t *to = (uint32_t *)(sega_framebuffer + (168 + y - 24) * 480 + 160);
                for (int x = 0; x < 80; x++)
                    to[x] = sega_pixels[48+x*2] | ((uint32_t)sega_pixels[49+x*2] << 16);
            }
        }
        return;
    }
    int x, start, w, h;
    SMS_get_pixel_region(&sega, &x, &start, &w, &h);
    if (y < 0 || y >= h || h > 240) return;
    if (sega_scale == 2) {
        retro_line2(sega_framebuffer, y, (480 - h * 2) / 2, sega_pixels, sega_line);
    } else {
        uint32_t *to = (uint32_t *)(sega_framebuffer + ((480 - h) / 2 + y) * 480 + 112);
        for (int x = 0; x < 128; x++)
            to[x] = sega_pixels[x * 2] | ((uint32_t)sega_pixels[x * 2 + 1] << 16);
    }
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(frame_obj, 6, 6, frame);
static mp_obj_t state_size(void) { return mp_obj_new_int(SMS_get_state_size(&sega, NULL)); }
static MP_DEFINE_CONST_FUN_OBJ_0(state_size_obj, state_size);
static mp_obj_t save_state(mp_obj_t obj) {
    mp_buffer_info_t b; mp_get_buffer_raise(obj, &b, MP_BUFFER_WRITE);
    if (!SMS_savestate(&sega, b.buf, b.len, NULL)) mp_raise_ValueError(MP_ERROR_TEXT("Sega: save state failed"));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(save_state_obj, save_state);
static mp_obj_t load_state(mp_obj_t obj) {
    mp_buffer_info_t b; mp_get_buffer_raise(obj, &b, MP_BUFFER_READ);
    if (!SMS_loadstate(&sega, b.buf, b.len, NULL)) mp_raise_ValueError(MP_ERROR_TEXT("Sega: load state failed"));
    SMS_skip_audio(&sega, true);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(load_state_obj, load_state);

// One call after EVERY emulated frame, including frames without video.
// Output packed PWM CC words for GPIO43 (slice 9, channel B), like gbaudio.
static mp_obj_t audio(mp_obj_t out, mp_obj_t top_obj, mp_obj_t volume_obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(out, &b, MP_BUFFER_WRITE);
    int top = mp_obj_get_int(top_obj), volume = mp_obj_get_int(volume_obj);
    if (b.len != AUDIO_SAMPLES * 4 || ((uintptr_t)b.buf & 3) ||
        top < 1 || top > 65535 || volume < 0 || volume > 100)
        mp_raise_ValueError(MP_ERROR_TEXT("Sega audio: buffer/top/volume"));
    int16_t pcm[AUDIO_SAMPLES];
    psg_take(pcm);
    uint32_t *dst = b.buf;
    for (unsigned i = 0; i < AUDIO_SAMPLES; i++) {
        int mono = (int)pcm[i] * volume / 100;
        uint32_t duty = ((uint32_t)(mono + 32768) * top) >> 16;
        dst[i] = duty << 16;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(audio_obj, audio);
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_init, MP_OBJ_FROM_PTR(&init_obj));
    mp_store_global(MP_QSTR_set_ram, MP_OBJ_FROM_PTR(&set_ram_obj));
    mp_store_global(MP_QSTR_get_ram, MP_OBJ_FROM_PTR(&get_ram_obj));
    mp_store_global(MP_QSTR_save_needed, MP_OBJ_FROM_PTR(&save_needed_obj));
    mp_store_global(MP_QSTR_palette, MP_OBJ_FROM_PTR(&palette_obj));
    mp_store_global(MP_QSTR_frame, MP_OBJ_FROM_PTR(&frame_obj));
    mp_store_global(MP_QSTR_state_size, MP_OBJ_FROM_PTR(&state_size_obj));
    mp_store_global(MP_QSTR_save_state, MP_OBJ_FROM_PTR(&save_state_obj));
    mp_store_global(MP_QSTR_load_state, MP_OBJ_FROM_PTR(&load_state_obj));
    mp_store_global(MP_QSTR_audio, MP_OBJ_FROM_PTR(&audio_obj));
    mp_store_global(MP_QSTR_audio_samples, mp_obj_new_int(AUDIO_SAMPLES));
    mp_store_global(MP_QSTR_audio_rate, mp_obj_new_int(AUDIO_RATE));
    mp_store_global(MP_QSTR_state_id, mp_obj_new_str("presto-sms-v1", sizeof("presto-sms-v1")-1));
    MP_DYNRUNTIME_INIT_EXIT
}
