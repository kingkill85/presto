// The few libc functions GCC calls on its own (copy loops become memcpy):
// native modules are linked without a C library.

#include <stddef.h>
#include <stdint.h>

void *memcpy(void *dst, const void *src, size_t n) {
    uint8_t *d = dst;
    const uint8_t *s = src;
    if ((((uintptr_t)d | (uintptr_t)s | n) & 3) == 0) {  // aligned: word by word
        uint32_t *dw = dst;
        const uint32_t *sw = src;
        for (n >>= 2; n; n--) {
            *dw++ = *sw++;
        }
        return dst;
    }
    while (n--) {
        *d++ = *s++;
    }
    return dst;
}

void *memmove(void *dst, const void *src, size_t n) {
    uint8_t *d = dst;
    const uint8_t *s = src;
    if (d < s) {
        while (n--) {
            *d++ = *s++;
        }
    } else {
        d += n;
        s += n;
        while (n--) {
            *--d = *--s;
        }
    }
    return dst;
}

void *memset(void *dst, int c, size_t n) {
    uint8_t *d = dst;
    while (n--) {
        *d++ = (uint8_t)c;
    }
    return dst;
}

int memcmp(const void *a, const void *b, size_t n) {
    const uint8_t *x = a, *y = b;
    for (; n; n--, x++, y++) {
        if (*x != *y) {
            return *x - *y;
        }
    }
    return 0;
}

int strncmp(const char *a, const char *b, size_t n) {
    while (n--) {
        unsigned char x = *a++, y = *b++;
        if (x != y) return x - y;
        if (!x) return 0;
    }
    return 0;
}

// GCC lowers __builtin_parity to this helper on Cortex-M33.
int __paritysi2(unsigned value) {
    value ^= value >> 16;
    value ^= value >> 8;
    value ^= value >> 4;
    return (0x6996 >> (value & 15)) & 1;
}
