// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void scumm_heap_begin(void *base, size_t size);
void scumm_heap_end(void);
void scumm_runtime_fail(const char *message) __attribute__((noreturn));
void scumm_runtime_yield(void);
int scumm_runtime_probe(unsigned rounds);
int scumm_file_probe(const char *path);
void scumm_runtime_reset(void);
#ifdef __cplusplus
}
#endif
