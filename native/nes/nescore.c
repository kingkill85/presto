// InfoNES adapter. Scanline-based rendering, own APU (presto_apu.h). See UPSTREAM.txt.
#include "../common/mpy_alloc.h"
#include "../common/retro_fb.h"
static void retro_nes_line(int y, const uint16_t *src);
#include "vendor/InfoNES.c"
#include "vendor/InfoNES_Mapper.c"
#include "vendor/K6502.c"
#include "palette.h"
// DMC samples are read when they play, from the PRG banks mapped at that
// scanline (the console fetches them in real time; reading all of a frame's
// bytes at vsync differed for ~0.2% of SMB3's DMC bytes).
static BYTE nes_dmc_read(uint16_t addr, unsigned cycle);
#define APU_DMC_READ(addr, cycle) nes_dmc_read(addr, cycle)
#include "presto_apu.h"
BYTE *apu_line_banks[APU_LINES][4];
static BYTE nes_dmc_read(uint16_t addr, unsigned cycle) {
    unsigned line = (cycle * APU_FRAME_LINES / APU_FRAME_CYCLES + APU_VSYNC_LINE + 1) % APU_FRAME_LINES;
    BYTE *bank = apu_line_banks[line][(addr >> 13) & 3];
    return bank && addr >= 0x8000 ? bank[addr & 0x1fff] : K6502_Read(addr);
}

WORD NesPalette[64];
uint16_t nes_pens[64];
unsigned nes_keys;
int nes_save_size;
uint16_t *nes_framebuffer;
unsigned nes_scale;
uint32_t nes_rom_fingerprint;

// APU glue: writes go to presto_apu.h; frame IRQ stays in the core. The
// former silent APU fields remain only to keep the state layout (state.h).
BYTE ApuC1Atl, ApuC2Atl, ApuC3a, ApuC3Atl, ApuC4Atl;
DWORD ApuC3Llc;
int ApuQuality;
static void apu_write(WORD addr, BYTE value) { apu_queue(addr & 0x1f, value); }
ApuWritefunc pAPUSoundRegs[20];  // filled at init: no pointer relocations in data
void ApuWriteControl(WORD addr, BYTE value) { apu_queue(0x15, value); }
// Reset/state load: silent APU and no bank pointers into a previous ROM.
static void nes_apu_reset(void) {
    memset(apu_line_banks, 0, sizeof(apu_line_banks));
    apu_reset();
}
void InfoNES_pAPUInit(void) {
    for (int i = 0; i < 20; i++) pAPUSoundRegs[i] = apu_write;
    APU_Mute = 0;
    nes_apu_reset();
}
void InfoNES_pAPUDone(void) {}
void InfoNES_pAPUVsync(void) { apu_frame(); }
int InfoNES_Menu(void) { return -1; }
int InfoNES_ReadRom(const char *name) { return -1; }
void InfoNES_ReleaseRom(void) {}
void InfoNES_LoadFrame(void) {}
void InfoNES_PadState(DWORD *a, DWORD *b, DWORD *system) {
    *a = nes_keys; *b = 0; *system = PAD_SYS_QUIT; // yield exactly once per emulated frame
}
void *InfoNES_MemoryCopy(void *dst, const void *src, int n) { return memcpy(dst, src, n); }
void *InfoNES_MemorySet(void *dst, int c, int n) { return memset(dst, c, n); }
void InfoNES_DebugPrint(char *message) {}
// Called once per scanline (after HSync): remember the PRG mapping for DMC.
void InfoNES_Wait(void) {
    BYTE **b = apu_line_banks[PPU_Scanline % APU_LINES];
    b[0] = ROMBANK0; b[1] = ROMBANK1; b[2] = ROMBANK2; b[3] = ROMBANK3;
}
void InfoNES_MessageBox(char *message, ...) {}
void InfoNES_SoundInit(void) {}
int InfoNES_SoundOpen(int a, int b) { return 0; }
void InfoNES_SoundClose(void) {}
void InfoNES_SoundOutput(int n, BYTE *a, BYTE *b, BYTE *c, BYTE *d, BYTE *e) {}

static mp_obj_t init(mp_obj_t rom_in) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(rom_in, &b, MP_BUFFER_READ);
    const uint8_t *p = b.buf;
    if (b.len < 16 || memcmp(p, "NES\x1a", 4) || !p[4]) {
        mp_raise_ValueError(MP_ERROR_TEXT("NES: invalid cartridge header"));
    }
    bool nes2 = (p[7] & 0x0c) == 8;
    // Extended sizes/submappers need hardware behavior this compact port lacks.
    // Accept ordinary NTSC NES 2.0 dumps such as SMB3 without rewriting the ROM.
    if (nes2 && (p[8] || p[9] || (p[10] & 15) > 7 || (p[10] >> 4) > 7 ||
                 p[11] > 7 || (p[12] & 1))) {
        mp_raise_ValueError(MP_ERROR_TEXT("NES: unsupported NES 2 configuration"));
    }
    unsigned mapper = (p[6] >> 4) | (p[7] & 0xf0);
    if (!(mapper == 0 || mapper == 1 || mapper == 2 || mapper == 3 || mapper == 4 || mapper == 7) ||
        ((mapper == 3 || mapper == 4) && p[5] == 0)) {
        mp_raise_ValueError(MP_ERROR_TEXT("NES: unsupported mapper or CHR configuration"));
    }
    size_t offset = 16 + ((p[6] & 4) ? 512 : 0);
    if (b.len < offset + p[4] * 16384u + p[5] * 8192u) {
        mp_raise_ValueError(MP_ERROR_TEXT("NES: truncated ROM"));
    }
    nes_rom_fingerprint = 2166136261u;
    for (size_t i = 0; i < b.len; i++) nes_rom_fingerprint = (nes_rom_fingerprint ^ p[i]) * 16777619u;
    memcpy(&NesHeader, p, 16);
    memset(NesHeader.byReserve, 0, sizeof(NesHeader.byReserve));
    ROM = (BYTE *)p + offset;
    VROM = p[5] ? ROM + p[4] * 16384u : PPURAM;
    memset(SRAM, 0, sizeof(SRAM));
    memset(chr_cache_tags, 0, sizeof(chr_cache_tags));
    memset(pbyPrevBank, 0, sizeof(pbyPrevBank));
    chr_cache_next = 0;
    for (int bank = 0; bank < 8; bank++) chr_bank_data[bank] = ChrBuf + bank * 4096;
    InfoNES_Init();
    if (InfoNES_Reset() != 0) mp_raise_ValueError(MP_ERROR_TEXT("NES: reset failed"));
    if (p[6] & 4) memcpy(SRAM + 0x1000, p + 16, 512);
    for (int i = 0; i < 64; i++) {
        NesPalette[i] = i; // bit 15 is reserved for InfoNES sprite priority
        nes_pens[i] = retro_pen(palette_rgb[i][0], palette_rgb[i][1], palette_rgb[i][2]);
    }
    nes_save_size = (p[6] & 2) ? sizeof(SRAM) : 0;
    return mp_obj_new_int(nes_save_size);
}
static MP_DEFINE_CONST_FUN_OBJ_1(init_obj, init);
static mp_obj_t set_ram(mp_obj_t obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(obj, &b, MP_BUFFER_READ);
    if (b.len != sizeof(SRAM)) mp_raise_ValueError(MP_ERROR_TEXT("NES: save size"));
    memcpy(SRAM, b.buf, b.len);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(set_ram_obj, set_ram);
static mp_obj_t get_ram(void) {
    return nes_save_size ? mp_obj_new_bytearray_by_ref(sizeof(SRAM), SRAM) : mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(get_ram_obj, get_ram);
static mp_obj_t chr_stats(void) {
    mp_obj_t result[] = {mp_obj_new_int(chr_calls), mp_obj_new_int(chr_banks)};
    chr_calls = chr_banks = 0;
    return mp_obj_new_tuple(2, result);
}
static MP_DEFINE_CONST_FUN_OBJ_0(chr_stats_obj, chr_stats);
static mp_obj_t palette(size_t n, const mp_obj_t *args) { return mp_const_none; }
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(palette_obj, 4, 4, palette);
static mp_obj_t frame(size_t n, const mp_obj_t *args) {
    nes_framebuffer = retro_fb(args[0]);
    nes_scale = mp_obj_get_int(args[5]) == 2 ? 2 : 1;
    unsigned keys = mp_obj_get_int(args[1]);
    nes_keys = (keys & 15) | ((keys & 64) >> 2) | ((keys & 128) >> 2) |
        ((keys & 32) << 1) | ((keys & 16) << 3);
    PAD1_Latch = nes_keys;
    bool draw = mp_obj_is_true(args[4]);
    FrameCnt = draw ? 0 : 1;
    FrameSkip = draw ? 0 : 1;
    WORD scanline[NES_DISP_WIDTH];
    WorkFrame = scanline;
    InfoNES_Cycle();
    WorkFrame = NULL;

    return mp_const_none;
}

static void retro_nes_line(int y, const uint16_t *src) {
    if ((unsigned)y >= 240) return;
    if (nes_scale == 2) {
        // Pens once per line onto the stack (nes_pens is heap PSRAM), then
        // both rows in one pass, two pixels per 64-bit store.
        uint32_t pens[64];
        for (int i = 0; i < 64; i++) pens[i] = nes_pens[i];
        uint64_t *a = (uint64_t *)(nes_framebuffer + y * 2 * 480);
        uint64_t *b = a + 120;
        for (int x = 0; x < 120; x++) {
            uint32_t p = pens[src[2 * x + 8] & 63], q = pens[src[2 * x + 9] & 63];
            uint64_t w = (p | (p << 16)) | ((uint64_t)(q | (q << 16)) << 32);
            a[x] = w;
            b[x] = w;
        }
        return;
    }
    uint32_t *to = (uint32_t *)(nes_framebuffer + (120 + y) * 480 + 112);
    for (int x = 0; x < 256; x += 2)
        to[x / 2] = nes_pens[src[x] & 63] | ((uint32_t)nes_pens[src[x + 1] & 63] << 16);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(frame_obj, 6, 6, frame);

// One call after EVERY emulated frame: the frame's samples as PWM CC words
// for GPIO43 (slice 9, channel B), like gbaudio and smscore.
static mp_obj_t audio(mp_obj_t out, mp_obj_t top_obj, mp_obj_t volume_obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(out, &b, MP_BUFFER_WRITE);
    int top = mp_obj_get_int(top_obj), volume = mp_obj_get_int(volume_obj);
    if (b.len != AUDIO_SAMPLES * 4 || ((uintptr_t)b.buf & 3) ||
        top < 1 || top > 65535 || volume < 0 || volume > 100)
        mp_raise_ValueError(MP_ERROR_TEXT("NES audio: buffer/top/volume"));
    uint32_t *dst = b.buf;
    for (unsigned i = 0; i < AUDIO_SAMPLES; i++) {
        int mono = (int)apu_out[i] * volume / 100;
        uint32_t duty = ((uint32_t)(mono + 32768) * top) >> 16;
        dst[i] = duty << 16;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(audio_obj, audio);
#include "state.h"

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_chr_stats, MP_OBJ_FROM_PTR(&chr_stats_obj));
    mp_store_global(MP_QSTR_init, MP_OBJ_FROM_PTR(&init_obj));
    mp_store_global(MP_QSTR_set_ram, MP_OBJ_FROM_PTR(&set_ram_obj));
    mp_store_global(MP_QSTR_get_ram, MP_OBJ_FROM_PTR(&get_ram_obj));
    mp_store_global(MP_QSTR_palette, MP_OBJ_FROM_PTR(&palette_obj));
    mp_store_global(MP_QSTR_frame, MP_OBJ_FROM_PTR(&frame_obj));
    mp_store_global(MP_QSTR_state_size, MP_OBJ_FROM_PTR(&state_size_obj));
    mp_store_global(MP_QSTR_save_state, MP_OBJ_FROM_PTR(&save_state_obj));
    mp_store_global(MP_QSTR_load_state, MP_OBJ_FROM_PTR(&load_state_obj));
    mp_store_global(MP_QSTR_audio, MP_OBJ_FROM_PTR(&audio_obj));
    mp_store_global(MP_QSTR_audio_samples, mp_obj_new_int(AUDIO_SAMPLES));
    mp_store_global(MP_QSTR_audio_rate, mp_obj_new_int(AUDIO_RATE));
    mp_store_global(MP_QSTR_state_id, mp_obj_new_str("presto-nes-v1", sizeof("presto-nes-v1")-1));
    MP_DYNRUNTIME_INIT_EXIT
}
