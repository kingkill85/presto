// SPDX-License-Identifier: GPL-2.0-or-later
// Read-only bridge to MicroPython's already-mounted VFS. Callback owns handles.
#include "py/dynruntime.h"
#include "frank_quest_fs.h"
#include <string.h>
extern mp_obj_t scumm_callback;

static mp_obj_t call(unsigned op, mp_obj_t a, mp_obj_t b) {
    mp_obj_t args[] = {mp_obj_new_int(op), a, b};
    return mp_call_function_n_kw(scumm_callback, 3, 0, args);
}
static mp_obj_t handle(CabalFile *file) {
    return mp_obj_new_int((uintptr_t)file);
}
CabalFile *cabal_file_open(const char *path) {
    mp_obj_t result = call(0, mp_obj_new_str(path, strlen(path)), mp_const_none);
    return (CabalFile *)(uintptr_t)mp_obj_get_int(result);
}
void cabal_file_close(CabalFile *file) {
    call(1, handle(file), mp_const_none);
}
int32_t cabal_file_read(CabalFile *file, void *buffer, uint32_t size) {
    mp_obj_t view = mp_obj_new_bytearray_by_ref(size, buffer);
    return mp_obj_get_int(call(2, handle(file), view));
}
uint32_t cabal_file_tell(CabalFile *file) {
    return mp_obj_get_int(call(3, handle(file), mp_const_none));
}
uint32_t cabal_file_size(CabalFile *file) {
    return mp_obj_get_int(call(4, handle(file), mp_const_none));
}
CabalFsResult cabal_file_seek(CabalFile *file, uint32_t offset) {
    return mp_obj_get_int(call(5, handle(file), mp_obj_new_int_from_uint(offset)));
}
