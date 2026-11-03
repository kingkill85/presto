// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdlib>
#include <new>
#include "runtime.h"
#include "common/memstream.h"
#include "backends/fs/rp2350/rp2350-fs.h"

namespace Common { class MemoryPool; extern MemoryPool *g_refCountPool; }
extern "C" void scumm_runtime_reset(void) {
    // The upstream string reference-count pool otherwise survives its arena.
    // Call only after the session's objects have been discarded.
    Common::g_refCountPool = nullptr;
}

void *operator new(size_t n) {
    void *p = malloc(n);
    if (!p) scumm_runtime_fail("SCUMM arena exhausted");
    return p;
}
void *operator new[](size_t n) { return ::operator new(n); }
void operator delete(void *p) noexcept { free(p); }
void operator delete[](void *p) noexcept { free(p); }
void operator delete(void *p, size_t) noexcept { free(p); }
void operator delete[](void *p, size_t) noexcept { free(p); }
extern "C" void __cxa_pure_virtual() { scumm_runtime_fail("SCUMM pure virtual call"); }
void error(const char *, ...) {
    scumm_runtime_fail("SCUMM stream runtime error");
    __builtin_unreachable();
}

// Intentionally initialized and mutable: verifies RAM relocation, including
// a pointer to the datum. Never assume flash-backed read-only module storage.
unsigned scumm_runtime_cookie = 0x13579bdf;
unsigned *scumm_runtime_cookie_ptr = &scumm_runtime_cookie;

extern "C" int scumm_runtime_probe(unsigned rounds) {
    const unsigned initial = *scumm_runtime_cookie_ptr;
    for (unsigned r = 0; r < rounds; ++r) {
        byte *data = new byte[32768];
        for (unsigned i = 0; i < 32768; ++i) data[i] = (i * 17 + r) & 255;
        // Real upstream polymorphic stream, with virtual inheritance and
        // delete-through-base. The stream owns the arena allocation.
        Common::SeekableReadStream *stream = new Common::MemoryReadStream(
            data, 32768, DisposeAfterUse::YES);
        scumm_runtime_yield(); // Python allocates and GC.collects here.
        if (!stream->seek(31337) || stream->readByte() != ((31337 * 17 + r) & 255))
            return -1;
        if (stream->size() != 32768 || stream->pos() != 31338) return -2;
        if (!stream->seek(-4, SEEK_END)) return -3;
        for (unsigned i = 32764; i < 32768; ++i)
            if (stream->readByte() != ((i * 17 + r) & 255)) return -4;
        if (stream->eos()) return -5;
        stream->readByte();
        if (!stream->eos()) return -6;
        stream->clearErr();
        delete stream;
        // Reallocation, zero-fill, fragmentation and exhausted-arena handling.
        void *blocks[32];
        for (unsigned i = 0; i < 32; ++i) {
            blocks[i] = calloc(1, 13 + i * 19);
            if (!blocks[i]) return -7;
            for (unsigned j = 0; j < 13 + i * 19; ++j)
                if (((byte *)blocks[i])[j]) return -8;
            ((byte *)blocks[i])[0] = i;
        }
        for (unsigned i = 0; i < 32; i += 2) free(blocks[i]);
        for (unsigned i = 1; i < 32; i += 2) {
            void *p = realloc(blocks[i], 2048 + i);
            if (!p || ((byte *)p)[0] != i) return -9;
            free(p);
        }
        if (malloc(0x40000000)) return -10;
        ++*scumm_runtime_cookie_ptr;
    }
    return *scumm_runtime_cookie_ptr == initial + rounds ? 1 : -11;
}

extern "C" int scumm_file_probe(const char *path) {
    Common::SeekableReadStream *s = RP2350::RP2350FileStream::makeFromPath(path);
    if (!s) return -20;
    if (s->size() != 32768 || s->pos() != 0) return -21;
    // Small reads use the upstream 4 KiB buffer, large ones bypass it.
    for (unsigned i = 0; i < 123; ++i)
        if (s->readByte() != ((i * 17) & 255)) return -22;
    byte *block = new byte[8192];
    if (s->read(block, 8192) != 8192 || s->pos() != 8315) return -23;
    for (unsigned i = 0; i < 8192; ++i)
        if (block[i] != (((i + 123) * 17) & 255)) return -24;
    delete[] block;
    if (!s->seek(-100, SEEK_CUR) || s->pos() != 8215) return -25;
    if (s->readByte() != ((8215 * 17) & 255)) return -26;
    if (!s->seek(-1, SEEK_END) || s->readByte() != ((32767 * 17) & 255)) return -27;
    s->readByte();
    if (!s->eos()) return -28;
    if (!s->seek(4) || s->eos() || s->readByte() != 68) return -29;
    delete s;
    return 1;
}
