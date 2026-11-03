// Runtime allocation for vendored C libraries, without a linked libc.
#pragma once
#include "py/dynruntime.h"
#include <stdlib.h>
#include <string.h>
static inline void *retro_calloc(size_t n, size_t size) {
    if (size && n > SIZE_MAX / size) mp_raise_ValueError(MP_ERROR_TEXT("allocation overflow"));
    void *p = m_malloc(n * size);
    memset(p, 0, n * size);
    return p;
}
#define malloc(n) m_malloc(n)
#define calloc(n, s) retro_calloc(n, s)
#define realloc(p, n) m_realloc(p, n)
#define free(p) m_free(p)
