// SPDX-License-Identifier: GPL-2.0-or-later
// Experimental decoder, runtime and SD stream probes, not a game engine.
#include "py/dynruntime.h"
#include "runtime.h"
mp_obj_t scumm_callback;
void scumm_runtime_fail(const char *message) {
    mp_raise_msg(&mp_type_RuntimeError, message);
}
void scumm_runtime_yield(void) {
    mp_call_function_n_kw(scumm_callback, 0, 0, NULL);
}
static mp_obj_t runtime_test(mp_obj_t arena, mp_obj_t callback, mp_obj_t rounds_obj) {
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arena, &buf, MP_BUFFER_WRITE);
    mp_int_t rounds = mp_obj_get_int(rounds_obj);
    if (rounds < 1 || rounds > 10000) mp_raise_ValueError("rounds must be 1..10000");
    scumm_heap_begin(buf.buf, buf.len);
    scumm_callback = callback;
    // MicroPython's dynruntime ABI has no NLR try/finally. A callback exception
    // aborts this call: caller MUST invoke close() from a Python finally block
    // while retaining the arena. C++ destructors cannot unwind across Python.
    int result = scumm_runtime_probe(rounds);
    scumm_runtime_reset();
    scumm_heap_end();
    scumm_callback = MP_OBJ_NULL;
    return mp_obj_new_int(result);
}
static MP_DEFINE_CONST_FUN_OBJ_3(runtime_test_obj, runtime_test);
static mp_obj_t file_test(mp_obj_t arena, mp_obj_t callback, mp_obj_t path) {
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arena, &buf, MP_BUFFER_WRITE);
    const char *name = mp_obj_str_get_str(path);
    scumm_heap_begin(buf.buf, buf.len);
    scumm_callback = callback;
    int result = scumm_file_probe(name);
    scumm_runtime_reset();
    scumm_heap_end();
    scumm_callback = MP_OBJ_NULL;
    return mp_obj_new_int(result);
}
static MP_DEFINE_CONST_FUN_OBJ_3(file_test_obj, file_test);
static mp_obj_t close_runtime(void) {
    scumm_runtime_reset();
    scumm_heap_end();
    scumm_callback = MP_OBJ_NULL;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(close_runtime_obj, close_runtime);
extern int scumm_bomp_probe(void);
static mp_obj_t self_test(void) {
    return mp_obj_new_int(scumm_bomp_probe());
}
static MP_DEFINE_CONST_FUN_OBJ_0(self_test_obj, self_test);
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_self_test, MP_OBJ_FROM_PTR(&self_test_obj));
    mp_store_global(MP_QSTR_runtime_test, MP_OBJ_FROM_PTR(&runtime_test_obj));
    mp_store_global(MP_QSTR_file_test, MP_OBJ_FROM_PTR(&file_test_obj));
    mp_store_global(MP_QSTR_close, MP_OBJ_FROM_PTR(&close_runtime_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
