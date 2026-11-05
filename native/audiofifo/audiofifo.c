// RP2350 PSRAM audio via the XIP auxiliary FIFO. No IRQ callbacks or retained pointers.
#include "py/dynruntime.h"
#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define XIP 0x400c8000u
#define AUX 0x50500000u
#define DMA 0x50000000u
#define BUSY (1u << 26)

static mp_buffer_info_t buffer(mp_obj_t obj) {
    mp_buffer_info_t b;
    mp_get_buffer_raise(obj, &b, MP_BUFFER_READ);
    uintptr_t p = (uintptr_t)b.buf;
    if ((p & 3) || b.len < 16 || (b.len & 3) || p < 0x11000000u ||
        p >= 0x11800000u || b.len > 0x11800000u - p) {
        mp_raise_ValueError(MP_ERROR_TEXT("aligned PSRAM buffer required"));
    }
    return b;
}

static mp_obj_t clean(mp_obj_t obj) {
    mp_buffer_info_t b = buffer(obj);
    uintptr_t end = ((uintptr_t)b.buf + b.len + 7) & ~(uintptr_t)7;
    // RP2350 clean-by-address, 8-byte lines; streamer bypasses the CPU cache.
    for (uintptr_t p = (uintptr_t)b.buf & ~(uintptr_t)7; p < end; p += 8) {
        *(volatile uint8_t *)(0x18000000u + p - 0x10000000u + 3) = 0;
    }
    __asm volatile("dsb\nisb" ::: "memory");
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(clean_obj, clean);

// current DMA is already configured, inactive and self-chained. previous=-1
// starts a new queue; otherwise append without dropping its final FIFO words.
static mp_obj_t queue(mp_obj_t obj, mp_obj_t prev_obj, mp_obj_t curr_obj) {
    mp_buffer_info_t b = buffer(obj);
    int prev = mp_obj_get_int(prev_obj), curr = mp_obj_get_int(curr_obj);
    if (prev < -1 || prev > 15 || curr < 0 || curr > 15 || prev == curr) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid audio DMA channels"));
    }
    uintptr_t c = DMA + (uint32_t)curr * 64;
    if (REG(XIP + 0x18) || (REG(c + 0x0c) & BUSY)) {
        mp_raise_ValueError(MP_ERROR_TEXT("audio stream busy"));
    }
    REG(XIP + 0x14) = (uintptr_t)b.buf;
    REG(XIP + 0x18) = b.len / 4;
    unsigned budget = 1000000;
    while (!(REG(XIP + 8) & 4) && --budget) {}
    if (!budget) {
        mp_raise_ValueError(MP_ERROR_TEXT("audio FIFO timeout"));
    }
    uint32_t irq;
    unsigned restart = 0;
    __asm volatile("mrs %0, primask\ncpsid i" : "=r"(irq) :: "memory");
    if (prev >= 0) {
        uintptr_t p = DMA + (uint32_t)prev * 64;
        // AL1_CTRL does not trigger. Clear read-only/error bits on writeback.
        REG(p + 0x10) = (REG(p + 0x10) & 0x1ffe1fffu) | ((uint32_t)curr << 13);
        if (!(REG(p + 0x0c) & BUSY) && !(REG(c + 0x0c) & BUSY)) {
            REG(c + 0x3c) = AUX;
            restart = 1;
        }
    } else {
        REG(c + 0x3c) = AUX;
    }
    __asm volatile("msr primask, %0" :: "r"(irq) : "memory");
    return mp_obj_new_int(restart);
}
static MP_DEFINE_CONST_FUN_OBJ_3(queue_obj, queue);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_clean, MP_OBJ_FROM_PTR(&clean_obj));
    mp_store_global(MP_QSTR_queue, MP_OBJ_FROM_PTR(&queue_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
