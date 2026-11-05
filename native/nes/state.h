// Pointer-free snapshots for the six supported InfoNES mappers.
// Included after the core definitions; never change vendor execution paths.
// Bump state_id and VERSION whenever the layout or interpretation changes.
#pragma once

#define NES_STATE_FIELDS(FIELD) \
    FIELD(PC) FIELD(SP) FIELD(F) FIELD(A) FIELD(X) FIELD(Y) \
    FIELD(IRQ_State) FIELD(IRQ_Wiring) FIELD(NMI_State) FIELD(NMI_Wiring) \
    FIELD(g_wPassedClocks) \
    FIELD(RAM) FIELD(SRAM) FIELD(PPURAM) FIELD(SPRRAM) \
    FIELD(PPU_R0) FIELD(PPU_R1) FIELD(PPU_R2) FIELD(PPU_R3) FIELD(PPU_R7) \
    FIELD(PPU_Scr_V) FIELD(PPU_Scr_V_Next) FIELD(PPU_Scr_V_Byte) \
    FIELD(PPU_Scr_V_Byte_Next) FIELD(PPU_Scr_V_Bit) FIELD(PPU_Scr_V_Bit_Next) \
    FIELD(PPU_Scr_H) FIELD(PPU_Scr_H_Next) FIELD(PPU_Scr_H_Byte) \
    FIELD(PPU_Scr_H_Byte_Next) FIELD(PPU_Scr_H_Bit) FIELD(PPU_Scr_H_Bit_Next) \
    FIELD(PPU_Addr) FIELD(PPU_Temp) FIELD(PPU_Increment) FIELD(PPU_Scanline) \
    FIELD(PPU_NameTableBank) FIELD(PPU_SP_Height) FIELD(SpriteJustHit) \
    FIELD(byVramWriteEnable) FIELD(PPU_Latch_Flag) FIELD(PPU_UpDown_Clip) \
    FIELD(FrameIRQ_Enable) FIELD(FrameStep) FIELD(FrameSkip) FIELD(FrameCnt) \
    FIELD(ChrBufUpdate) FIELD(PalTable) FIELD(APU_Reg) \
    FIELD(PAD1_Latch) FIELD(PAD2_Latch) FIELD(PAD_System) FIELD(PAD1_Bit) FIELD(PAD2_Bit) \
    FIELD(ApuC1Atl) FIELD(ApuC2Atl) FIELD(ApuC3a) FIELD(ApuC3Atl) FIELD(ApuC4Atl) FIELD(ApuC3Llc)

#define NES_MMC1_FIELDS(FIELD) \
    FIELD(Map1_Regs) FIELD(Map1_Cnt) FIELD(Map1_Latch) FIELD(Map1_Last_Write_Addr) \
    FIELD(Map1_Size) FIELD(Map1_256K_base) FIELD(Map1_swap) \
    FIELD(Map1_bank1) FIELD(Map1_bank2) FIELD(Map1_bank3) FIELD(Map1_bank4) \
    FIELD(Map1_HI1) FIELD(Map1_HI2)

#define NES_MMC3_FIELDS(FIELD) \
    FIELD(Map4_Regs) FIELD(Map4_Rom_Bank) FIELD(Map4_Prg0) FIELD(Map4_Prg1) \
    FIELD(Map4_Chr01) FIELD(Map4_Chr23) FIELD(Map4_Chr4) FIELD(Map4_Chr5) \
    FIELD(Map4_Chr6) FIELD(Map4_Chr7) FIELD(Map4_IRQ_Enable) FIELD(Map4_IRQ_Cnt) \
    FIELD(Map4_IRQ_Latch) FIELD(Map4_IRQ_Request) FIELD(Map4_IRQ_Present) FIELD(Map4_IRQ_Present_Vbl)

#define NES_DECLARE(name) __typeof__(name) name;
struct NesState {
    uint32_t magic, version, size, fingerprint, mapper;
    struct NesHeader_tag header;
    uint32_t prg[4], ppu[16], previous[8], bg, sp;
    NES_STATE_FIELDS(NES_DECLARE)
    NES_MMC1_FIELDS(NES_DECLARE)
    NES_MMC3_FIELDS(NES_DECLARE)
    // Only the eight currently mapped decoded banks, not the 128 KiB cache.
    uint8_t decoded[8][4096];
};
#undef NES_DECLARE

#define NES_STATE_MAGIC 0x3153454eU
#define NES_STATE_VERSION 1
#define NES_PTR_VROM 0x80000000U
#define NES_PTR_NULL 0xffffffffU

static void nes_state_error(void) {
    mp_raise_ValueError(MP_ERROR_TEXT("NES: invalid or incompatible state"));
}

static uint32_t nes_encode_bank(const BYTE *p, bool nullable) {
    uintptr_t value = (uintptr_t)p;
    if (!p && nullable) return NES_PTR_NULL;
    uintptr_t base = (uintptr_t)PPURAM;
    if (value >= base && value - base <= sizeof(PPURAM) - 1024 && !((value-base) & 1023))
        return value - base;
    base = (uintptr_t)VROM;
    size_t size = (size_t)NesHeader.byVRomSize * 8192;
    if (size >= 1024 && value >= base && value - base <= size - 1024 && !((value-base) & 1023))
        return NES_PTR_VROM | (value - base);
    nes_state_error();
    return 0;
}

static BYTE *nes_decode_bank(uint32_t offset, bool nullable) {
    if (offset == NES_PTR_NULL && nullable) return NULL;
    size_t size = offset & NES_PTR_VROM ? (size_t)NesHeader.byVRomSize * 8192 : sizeof(PPURAM);
    BYTE *base = offset & NES_PTR_VROM ? VROM : PPURAM;
    offset &= ~NES_PTR_VROM;
    if (size < 1024 || offset > size - 1024 || (offset & 1023)) nes_state_error();
    return base + offset;
}

static struct NesState *nes_state_buffer(mp_obj_t obj, int flags) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(obj, &b, flags);
    if (b.len != sizeof(struct NesState) || ((uintptr_t)b.buf & 3) || WorkFrame || !NesHeader.byRomSize)
        nes_state_error();
    return b.buf;
}

static mp_obj_t state_size(void) { return mp_obj_new_int(sizeof(struct NesState)); }
static MP_DEFINE_CONST_FUN_OBJ_0(state_size_obj, state_size);

static mp_obj_t save_state(mp_obj_t obj) {
    struct NesState *s = nes_state_buffer(obj, MP_BUFFER_WRITE);
    memset(s, 0, sizeof(*s)); // deterministic padding and inactive mapper fields
    s->magic = NES_STATE_MAGIC;
    s->version = NES_STATE_VERSION;
    s->size = sizeof(*s);
    s->fingerprint = nes_rom_fingerprint;
    s->mapper = MapperNo;
    s->header = NesHeader;
    BYTE *prg[] = {ROMBANK0, ROMBANK1, ROMBANK2, ROMBANK3};
    for (int i = 0; i < 4; i++) {
        uintptr_t p = (uintptr_t)prg[i], base = (uintptr_t)ROM;
        if (p < base || p - base > (size_t)NesHeader.byRomSize * 16384 - 8192 || ((p-base) & 8191))
            nes_state_error();
        s->prg[i] = p - base;
    }
    if (SRAMBANK != SRAM) nes_state_error(); // true for every supported mapper
    for (int i = 0; i < 16; i++) s->ppu[i] = nes_encode_bank(PPUBANK[i], false);
    for (int i = 0; i < 8; i++) {
        s->previous[i] = nes_encode_bank(pbyPrevBank[i], true);
        memcpy(s->decoded[i], chr_bank_data[i], 4096);
    }
    s->bg = PPU_BG_Base - ChrBuf;
    s->sp = PPU_SP_Base - ChrBuf;
#define NES_COPY_OUT(name) memcpy(&s->name, &name, sizeof(name));
    NES_STATE_FIELDS(NES_COPY_OUT)
    if (MapperNo == 1) { NES_MMC1_FIELDS(NES_COPY_OUT) }
    if (MapperNo == 4) { NES_MMC3_FIELDS(NES_COPY_OUT) }
#undef NES_COPY_OUT
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(save_state_obj, save_state);

static mp_obj_t load_state(mp_obj_t obj) {
    const struct NesState *s = nes_state_buffer(obj, MP_BUFFER_READ);
    // Complete validation before touching any emulated memory or registers.
    if (s->magic != NES_STATE_MAGIC || s->version != NES_STATE_VERSION || s->size != sizeof(*s) ||
        s->fingerprint != nes_rom_fingerprint || s->mapper != MapperNo ||
        memcmp(&s->header, &NesHeader, sizeof(NesHeader)) ||
        (s->bg != 0 && s->bg != 16384) || (s->sp != 0 && s->sp != 16384) ||
        s->PPU_Scanline > SCAN_VBLANK_END || s->PPU_NameTableBank > 15 ||
        (s->PPU_SP_Height != 8 && s->PPU_SP_Height != 16) ||
        (s->PPU_Increment != 1 && s->PPU_Increment != 32) ||
        s->PAD1_Bit > 23 || s->PAD2_Bit > 23 ||
        s->PPU_Scr_V_Bit > 7 || s->PPU_Scr_V_Bit_Next > 7 ||
        s->PPU_Scr_H_Bit > 7 || s->PPU_Scr_H_Bit_Next > 7 ||
        (MapperNo == 1 && (s->Map1_Cnt > 4 || s->Map1_Size > Map1_1024K)))
        nes_state_error();
    for (int i = 0; i < 4; i++)
        if (s->prg[i] > (size_t)NesHeader.byRomSize * 16384 - 8192 || (s->prg[i] & 8191))
            nes_state_error();
    BYTE *ppu[16], *previous[8];
    for (int i = 0; i < 16; i++) ppu[i] = nes_decode_bank(s->ppu[i], false);
    for (int i = 0; i < 8; i++) previous[i] = nes_decode_bank(s->previous[i], true);
#define NES_COPY_IN(name) memcpy(&name, &s->name, sizeof(name));
    NES_STATE_FIELDS(NES_COPY_IN)
    NES_MMC1_FIELDS(NES_COPY_IN)
    NES_MMC3_FIELDS(NES_COPY_IN)
#undef NES_COPY_IN
    // Mapper function pointers and constant CPU/scanline tables belong to the
    // freshly initialised current core. Never restore addresses from a file.
    SRAMBANK = SRAM;
    ROMBANK0 = ROM + s->prg[0]; ROMBANK1 = ROM + s->prg[1];
    ROMBANK2 = ROM + s->prg[2]; ROMBANK3 = ROM + s->prg[3];
    memcpy(PPUBANK, ppu, sizeof(ppu));
    PPU_BG_Base = ChrBuf + s->bg;
    PPU_SP_Base = ChrBuf + s->sp;
    memset(chr_cache_tags, 0, sizeof(chr_cache_tags));
    chr_cache_next = 0;
    chr_calls = chr_banks = 0;
    for (int i = 0; i < 8; i++) {
        chr_bank_data[i] = ChrBuf + i * 4096;
        memcpy(chr_bank_data[i], s->decoded[i], 4096);
        pbyPrevBank[i] = previous[i];
    }
    // The APU state is not part of v1 snapshots: restart it silent; the game's
    // next register writes bring the music back.
    APU_Mute = 0;
    nes_apu_reset();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(load_state_obj, load_state);
