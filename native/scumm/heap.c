// SPDX-License-Identifier: GPL-2.0-or-later
// The caller owns/root-pins the entire arena. C++ pointers are never GC roots.
#include "runtime.h"
#include <stdint.h>
extern void *create_mspace_with_base(void *, size_t, int);
extern size_t destroy_mspace(void *);
extern void *mspace_malloc(void *, size_t);
extern void *mspace_calloc(void *, size_t, size_t);
extern void *mspace_realloc(void *, void *, size_t);
extern void mspace_free(void *, void *);
void *scumm_heap;
#ifndef SCUMM_ENGINE
size_t strlen(const char *s) {
    const char *end = s;
    while (*end) ++end;
    return end - s;
}
#endif

void scumm_heap_begin(void *base, size_t size) {
    if (scumm_heap) scumm_runtime_fail("SCUMM runtime already active");
    if (size < 16384 || ((uintptr_t)base & 7))
        scumm_runtime_fail("SCUMM arena must be aligned and at least 16 KiB");
    scumm_heap = create_mspace_with_base(base, size, 0);
    if (!scumm_heap) scumm_runtime_fail("Cannot initialize SCUMM arena");
}
void scumm_heap_end(void) {
    if (scumm_heap) destroy_mspace(scumm_heap);
    scumm_heap = NULL;
}
void *malloc(size_t n) {
    if (!scumm_heap) scumm_runtime_fail("SCUMM allocation outside session");
    return mspace_malloc(scumm_heap, n);
}
void *calloc(size_t n, size_t size) {
    if (!scumm_heap) scumm_runtime_fail("SCUMM allocation outside session");
    return mspace_calloc(scumm_heap, n, size);
}
void *realloc(void *p, size_t n) {
    if (!scumm_heap) scumm_runtime_fail("SCUMM allocation outside session");
    return mspace_realloc(scumm_heap, p, n);
}
void free(void *p) {
    if (!p) return;
    if (!scumm_heap) scumm_runtime_fail("SCUMM free outside session");
    mspace_free(scumm_heap, p);
}
void abort(void) {
    scumm_runtime_fail("SCUMM allocator detected corruption");
    __builtin_unreachable();
}
void cabal_heap_error(void *heap, void *p) {
    (void)heap;
    (void)p;
    abort();
}
void cabal_heap_corruption(void *heap) {
    (void)heap;
    abort();
}
