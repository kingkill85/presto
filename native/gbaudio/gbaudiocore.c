// Shared DMG/CGB audio adapter: four-channel mixing and full states.
#include "vendor/minigb_apu.h"
struct minigb_apu_ctx apu;
static uint8_t audio_read(uint16_t addr);
static void audio_write(uint16_t addr, uint8_t value) {
    minigb_apu_audio_write(&apu, addr, value);
}
#define ENABLE_SOUND 1
#define GB_CUSTOM_MODULE 1
#ifdef GBC_AUDIO
#define AUDIO_STATE_ID "presto-gbc-audio-v2"
#include "../gbc/gbccore.c"
#else
#define AUDIO_STATE_ID "presto-gb-audio-v2"
#include "../gb/gbcore.c"
#endif

static uint8_t audio_read(uint16_t addr) {
    // Walnut's wide IO reads can cross the final APU register into LCD IO.
    // Delegate those bytes rather than indexing past MiniGB's register array.
    if (addr < 0xff10 || addr > 0xff3f) return __gb_read(&gb, addr);
    return minigb_apu_audio_read(&apu, addr);
}

static mp_obj_t audio_init(mp_obj_t obj) {
    memset(&apu, 0, sizeof(apu));
    // Upstream init writes NR52 last; power on before applying boot registers.
    minigb_apu_audio_write(&apu, 0xff26, 0x80);
    minigb_apu_audio_init(&apu);
    return init(obj);
}
static MP_DEFINE_CONST_FUN_OBJ_1(audio_init_obj, audio_init);

// One call after EVERY emulated frame, including frames without video.
// Output packed PWM CC words for GPIO43 (slice 9, channel B on RP2350).
// Caller owns the buffer and must keep it alive until DMA has finished.
static mp_obj_t audio(mp_obj_t out, mp_obj_t top_obj, mp_obj_t volume_obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(out, &b, MP_BUFFER_WRITE);
    int top = mp_obj_get_int(top_obj), volume = mp_obj_get_int(volume_obj);
    if (b.len != AUDIO_SAMPLES * 4 || ((uintptr_t)b.buf & 3) ||
        top < 1 || top > 65535 || volume < 0 || volume > 100)
        mp_raise_ValueError(MP_ERROR_TEXT("gb audio: buffer/top/volume"));
    audio_sample_t pcm[AUDIO_SAMPLES_TOTAL];
    minigb_apu_audio_callback(&apu, pcm);
    uint32_t *dst = b.buf;
    for (unsigned i = 0; i < AUDIO_SAMPLES; i++) {
        // Average stereo; attenuate before scaling to avoid signed overflow.
        int mono = ((int)pcm[i * 2] + pcm[i * 2 + 1]) / 2;
        mono = mono * volume / 100;
        uint32_t duty = ((uint32_t)(mono + 32768) * top) >> 16;
        dst[i] = duty << 16;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(audio_obj, audio);

// Audio-aware state layout; no DMA addresses or host pointers are serialized.
static mp_obj_t audio_state_size(void) {
    return mp_obj_new_int(sizeof(gb) + sizeof(apu) + cart_ram_len);
}
static MP_DEFINE_CONST_FUN_OBJ_0(audio_state_size_obj, audio_state_size);
static mp_obj_t audio_save_state(mp_obj_t obj) {
    mp_buffer_info_t b; mp_get_buffer_raise(obj, &b, MP_BUFFER_WRITE);
    if (b.len != sizeof(gb) + sizeof(apu) + cart_ram_len)
        mp_raise_ValueError(MP_ERROR_TEXT("gb audio: state size"));
    memcpy(b.buf, &gb, sizeof(gb));
    state_bind((struct gb_s *)b.buf, false);
    memcpy((uint8_t *)b.buf + sizeof(gb), &apu, sizeof(apu));
    if (cart_ram_len) memcpy((uint8_t *)b.buf + sizeof(gb) + sizeof(apu), cart_ram, cart_ram_len);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(audio_save_state_obj, audio_save_state);
static mp_obj_t audio_load_state(mp_obj_t obj) {
    mp_buffer_info_t b; mp_get_buffer_raise(obj, &b, MP_BUFFER_READ);
    if (b.len != sizeof(gb) + sizeof(apu) + cart_ram_len)
        mp_raise_ValueError(MP_ERROR_TEXT("gb audio: state size"));
    // Check arithmetic invariants before changing either emulated subsystem.
    struct minigb_apu_ctx restored;
    memcpy(&restored, (uint8_t *)b.buf + sizeof(gb), sizeof(restored));
    if (restored.vol_l < 0 || restored.vol_l > 7 || restored.vol_r < 0 || restored.vol_r > 7)
        mp_raise_ValueError(MP_ERROR_TEXT("gb audio: state volume"));
    for (unsigned i = 0; i < 4; ++i) {
        struct chan *c = &restored.chans[i];
        if (c->freq > 2047 || c->volume > 15 || c->volume_init > 15 ||
            c->enabled > 1 || c->powered > 1 || c->on_left > 1 || c->on_right > 1 ||
            (i < 2 && c->square.duty_counter > 7))
            mp_raise_ValueError(MP_ERROR_TEXT("gb audio: state channel"));
    }
    memcpy(&gb, b.buf, sizeof(gb));
    state_bind(&gb, true);
    memcpy(&apu, &restored, sizeof(apu));
    if (cart_ram_len) memcpy(cart_ram, (uint8_t *)b.buf + sizeof(gb) + sizeof(apu), cart_ram_len);
    error = 0;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(audio_load_state_obj, audio_load_state);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_init, MP_OBJ_FROM_PTR(&audio_init_obj));
    mp_store_global(MP_QSTR_set_ram, MP_OBJ_FROM_PTR(&set_ram_obj));
    mp_store_global(MP_QSTR_palette, MP_OBJ_FROM_PTR(&palette_obj));
    mp_store_global(MP_QSTR_frame, MP_OBJ_FROM_PTR(&frame_obj));
    mp_store_global(MP_QSTR_audio, MP_OBJ_FROM_PTR(&audio_obj));
    mp_store_global(MP_QSTR_audio_samples, mp_obj_new_int(AUDIO_SAMPLES));
    mp_store_global(MP_QSTR_audio_rate, mp_obj_new_int(22039));
    mp_store_global(MP_QSTR_state_size, MP_OBJ_FROM_PTR(&audio_state_size_obj));
    mp_store_global(MP_QSTR_save_state, MP_OBJ_FROM_PTR(&audio_save_state_obj));
    mp_store_global(MP_QSTR_load_state, MP_OBJ_FROM_PTR(&audio_load_state_obj));
    mp_store_global(MP_QSTR_state_id, mp_obj_new_str(AUDIO_STATE_ID, sizeof(AUDIO_STATE_ID)-1));
    MP_DYNRUNTIME_INIT_EXIT
}
