// Game Boy emulator core for the Presto: Peanut-GB (MIT, peanut_gb.h) as a
// MicroPython native module. Python hands over the ROM, the cartridge RAM
// (save game) and the framebuffer; every frame the core writes the 160x144
// picture into RGB565: unscaled in 240x240, or exactly 3x in 480x480.
//
//   size = gbcore.init(rom)          # returns the save RAM size in bytes
//   gbcore.set_ram(bytearray(size))  # optional: battery backed save RAM
//   gbcore.palette(p0, p1, p2, p3)   # pen values for the 4 shades
//   gbcore.frame(fb, keys, x, y, draw, fullscreen=False)

#include "py/dynruntime.h"

#define PEANUT_GB_IS_LITTLE_ENDIAN 1
#define ENABLE_SOUND 0
#define ENABLE_LCD 1
#include "peanut_gb.h"

#define FB_W 240
#define FB_H 240
#define FULL_W 480
#define FULL_H 480
#define SCALE 3
#define TOP ((FULL_H - LCD_HEIGHT * SCALE) / 2)

struct gb_s gb;
const uint8_t *rom;
size_t rom_len;
uint8_t *cart_ram;
size_t cart_ram_len;
uint16_t *fb;  // where line 0, pixel 0 goes
uint16_t shades[4];
int error;
int fullscreen;
// Expand in fast SRAM, then write whole words sequentially to display PSRAM.
// Alternating halfword stores between three distant rows is very expensive.
uint32_t expanded_line[FULL_W / 2];

void abort(void) {
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("gb: abort"));
    for (;;) {
    }
}

static uint8_t rom_read(struct gb_s *g, const uint_fast32_t addr) {
    return addr < rom_len ? rom[addr] : 0xFF;
}

static uint8_t ram_read(struct gb_s *g, const uint_fast32_t addr) {
    return addr < cart_ram_len ? cart_ram[addr] : 0xFF;
}

static void ram_write(struct gb_s *g, const uint_fast32_t addr, const uint8_t val) {
    if (addr < cart_ram_len) {
        cart_ram[addr] = val;
    }
}

static void on_error(struct gb_s *g, const enum gb_error_e err, const uint16_t addr) {
    error = 1 + (int)err;
}

static void draw_line(struct gb_s *g, const uint8_t *pixels, const uint_fast8_t line) {
    if (fullscreen) {
        uint16_t *row = fb + (TOP + line * SCALE) * FULL_W;
        for (int x = 0, out = 0; x < LCD_WIDTH; x += 2, out += 3) {
            uint32_t a = shades[pixels[x] & 3];
            uint32_t b = shades[pixels[x + 1] & 3];
            expanded_line[out] = a | (a << 16);
            expanded_line[out + 1] = a | (b << 16);
            expanded_line[out + 2] = b | (b << 16);
        }
        for (int y = 0; y < SCALE; y++) {
            uint32_t *to = (uint32_t *)(row + y * FULL_W);
            for (int x = 0; x < FULL_W / 2; x++) {
                to[x] = expanded_line[x];
            }
        }
        return;
    }
    uint16_t *to = fb + line * FB_W;
    for (int x = 0; x < LCD_WIDTH; x++) {
        to[x] = shades[pixels[x] & 3];
    }
}

static mp_obj_t init(mp_obj_t rom_in) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(rom_in, &b, MP_BUFFER_READ);
    rom = b.buf;
    rom_len = b.len;
    cart_ram = NULL;
    cart_ram_len = 0;
    error = 0;
    enum gb_init_error_e e = gb_init(&gb, rom_read, ram_read, ram_write, on_error, NULL);
    if (e != GB_INIT_NO_ERROR) {
        mp_raise_ValueError(MP_ERROR_TEXT("gb: can't start this ROM"));
    }
    gb_init_lcd(&gb, draw_line);
    size_t save = 0;
    if (gb_get_save_size_s(&gb, &save) != 0) {
        save = 0;
    }
    return mp_obj_new_int(save);
}
static MP_DEFINE_CONST_FUN_OBJ_1(init_obj, init);

static mp_obj_t set_ram(mp_obj_t ram_in) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(ram_in, &b, MP_BUFFER_WRITE);
    cart_ram = b.buf;
    cart_ram_len = b.len;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(set_ram_obj, set_ram);

static mp_obj_t palette(size_t n_args, const mp_obj_t *args) {
    for (int i = 0; i < 4 && i < (int)n_args; i++) {
        shades[i] = mp_obj_get_int(args[i]);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(palette_obj, 4, 4, palette);

// Fullscreen uses a 480x480 buffer, centered 3x pixels and untouched 24px bars.
// x and y must be zero. The original five-argument API still uses 240x240.
static mp_obj_t frame(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(args[0], &b, MP_BUFFER_WRITE);
    int x = mp_obj_get_int(args[2]), y = mp_obj_get_int(args[3]);
    fullscreen = n_args == 6 && mp_obj_is_true(args[5]);
    int stride = fullscreen ? FULL_W : FB_W;
    int rows = fullscreen ? FULL_H : FB_H;
    int width = fullscreen ? FULL_W : LCD_WIDTH;
    int height = fullscreen ? FULL_H : LCD_HEIGHT;
    if (b.len < stride * rows * 2 || (fullscreen && ((uintptr_t)b.buf & 3)) ||
        x < 0 || y < 0 || x + width > stride || y + height > rows) {
        mp_raise_ValueError(MP_ERROR_TEXT("gb: framebuffer"));
    }
    fb = (uint16_t *)b.buf + y * stride + x;
    gb.direct.joypad = ~mp_obj_get_int(args[1]) & 0xFF;  // the Game Boy wants 0 for pressed
    gb.display.lcd_draw_line = mp_obj_is_true(args[4]) ? draw_line : NULL;
    gb_run_frame(&gb);
    if (error) {
        int e = error;
        error = 0;
        return mp_obj_new_int(e);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(frame_obj, 5, 6, frame);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_init, MP_OBJ_FROM_PTR(&init_obj));
    mp_store_global(MP_QSTR_set_ram, MP_OBJ_FROM_PTR(&set_ram_obj));
    mp_store_global(MP_QSTR_palette, MP_OBJ_FROM_PTR(&palette_obj));
    mp_store_global(MP_QSTR_frame, MP_OBJ_FROM_PTR(&frame_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
