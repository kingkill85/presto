// SPDX-License-Identifier: GPL-2.0-or-later
#include "py/dynruntime.h"
#include "runtime.h"
#include "frank_quest_fs.h"
#include "backends/platform/rp2350/rp2350-minimal.h"
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

mp_obj_t scumm_callback;
bool scumm_used;
extern uint16_t *scumm_framebuffer;
extern bool scumm_zoom, scumm_zoom_dirty;
extern int scumm_engine_run(const char *path,int profile);
void scumm_runtime_fail(const char *message) { mp_raise_msg(&mp_type_RuntimeError, message); }
static mp_obj_t host(int op, mp_obj_t a, mp_obj_t b) {
    mp_obj_t args[] = {mp_obj_new_int(op), a, b};
    return mp_call_function_n_kw(scumm_callback,3,0,args);
}
long scumm_host_call(int op, long a, long b) {
    return mp_obj_get_int(host(op,mp_obj_new_int(a),mp_obj_new_int(b)));
}
bool cabal_poll_event(CabalEvent *event) {
    mp_obj_t result = host(103,mp_const_none,mp_const_none);
    if (result == mp_const_none) return false;
    size_t n; mp_obj_t *items;
    mp_obj_get_array(result,&n,&items);
    if (n != 3) scumm_runtime_fail("Bad SCUMM input event");
    memset(event,0,sizeof(*event));
    event->type = mp_obj_get_int(items[0]);
    if (event->type == CABAL_EVENT_KEYDOWN || event->type == CABAL_EVENT_KEYUP) {
        event->kbd.keycode=mp_obj_get_int(items[1]); event->kbd.ascii=mp_obj_get_int(items[2]);
    } else {
        event->mouse.x=mp_obj_get_int(items[1]); event->mouse.y=mp_obj_get_int(items[2]);
    }
    return true;
}
static mp_obj_t string(const char *s) { return mp_obj_new_str(s,strlen(s)); }
bool cabal_path_exists(const char *p) { return mp_obj_get_int(host(6,string(p),mp_const_none)) != 0; }
bool cabal_path_is_dir(const char *p) { return mp_obj_get_int(host(6,string(p),mp_const_none)) == 2; }
CabalDir *cabal_dir_open(const char *p) { return (CabalDir *)(uintptr_t)mp_obj_get_int(host(7,string(p),mp_const_none)); }
void cabal_dir_close(CabalDir *p) { scumm_host_call(9,(uintptr_t)p,0); }
bool cabal_dir_read(CabalDir *p, CabalDirEntry *entry) {
    mp_obj_t value = host(8,mp_obj_new_int((uintptr_t)p),mp_const_none);
    if (value == mp_const_none) return false;
    size_t n; mp_obj_t *items;
    mp_obj_get_array(value,&n,&items);
    if (n != 3) scumm_runtime_fail("Bad SCUMM directory entry");
    const char *name = mp_obj_str_get_str(items[0]);
    size_t len = strlen(name);
    if (len >= sizeof(entry->name)) scumm_runtime_fail("SCUMM filename too long");
    memcpy(entry->name,name,len+1);
    entry->size=mp_obj_get_int(items[1]); entry->isDirectory=mp_obj_is_true(items[2]);
    return true;
}
CabalFile *cabal_file_open_write(const char *p) { return (CabalFile *)(uintptr_t)mp_obj_get_int(host(10,string(p),mp_const_none)); }
int32_t cabal_file_write(CabalFile *p,const void *data,uint32_t n) {
    return mp_obj_get_int(host(11,mp_obj_new_int((uintptr_t)p),mp_obj_new_bytearray_by_ref(n,(void *)data)));
}
CabalFsResult cabal_file_flush(CabalFile *p) { return scumm_host_call(12,(uintptr_t)p,0); }
CabalFsResult cabal_mkdir(const char *p) { return mp_obj_get_int(host(13,string(p),mp_const_none)); }
CabalFsResult cabal_remove(const char *p) { return mp_obj_get_int(host(14,string(p),mp_const_none)); }
int __wrap_remove(const char *p) { return cabal_remove(p) ? -1 : 0; }

// Use newlib for formatting/math/string routines, never its heap or syscalls.
void *__wrap_malloc(size_t n) { return malloc(n); }
void *__wrap_calloc(size_t n,size_t size) { return calloc(n,size); }
void *__wrap_realloc(void *p,size_t n) { return realloc(p,n); }
void __wrap_free(void *p) { free(p); }
void *__wrap__malloc_r(void *r,size_t n) { (void)r;return malloc(n); }
void *__wrap__calloc_r(void *r,size_t n,size_t size) { (void)r;return calloc(n,size); }
void *__wrap__realloc_r(void *r,void *p,size_t n) { (void)r;return realloc(p,n); }
void __wrap__free_r(void *r,void *p) { (void)r;free(p); }
int __wrap_printf(const char *format,...) {
    va_list args;va_start(args,format);int n=mp_vprintf(&mp_plat_print,format,args);va_end(args);return n;
}
int __wrap_puts(const char *s) { return mp_printf(&mp_plat_print,"%s\n",s); }
int __wrap_fflush(void *p) { (void)p;return 0; }
void __wrap_exit(int status) { (void)status;scumm_runtime_fail("SCUMM engine stopped with an error"); }
void __wrap__exit(int status) { __wrap_exit(status); }
void __wrap_abort(void) { scumm_runtime_fail("SCUMM runtime aborted"); }
void *_sbrk(int n) { (void)n;return (void *)-1; }
int _write(int fd,const void *p,size_t n) { (void)fd;mp_plat_print.print_strn(mp_plat_print.data,p,n);return n; }
int _read(int fd,void *p,size_t n) { (void)fd;(void)p;(void)n;return -1; }
int _close(int fd) { (void)fd;return -1; }
int _lseek(int fd,int p,int w) { (void)fd;(void)p;(void)w;return -1; }
int _isatty(int fd) { (void)fd;return 1; }
int _fstat(int fd,void *p) { (void)fd;(void)p;return -1; }
int _getpid(void) { return 1; }
int _kill(int pid,int sig) { (void)pid;(void)sig;return -1; }

static mp_obj_t run(size_t n,const mp_obj_t *args) {
    if (scumm_used) scumm_runtime_fail("Reset before starting another SCUMM session");
    mp_buffer_info_t arena,fb;
    mp_get_buffer_raise(args[0],&arena,MP_BUFFER_WRITE);
    mp_get_buffer_raise(args[2],&fb,MP_BUFFER_WRITE);
    if (fb.len != 480*480*2) mp_raise_ValueError("SCUMM needs a 480x480 RGB565 framebuffer");
    const char *path=mp_obj_str_get_str(args[3]);
    (void)n;
    int profile=mp_obj_get_int(args[4]);
    if (profile<1 || profile>2) mp_raise_ValueError("Unknown SCUMM game profile");
    scumm_used=true;
    scumm_callback=args[1];scumm_framebuffer=fb.buf;
    scumm_heap_begin(arena.buf,arena.len);
    int result=scumm_engine_run(path,profile);
    scumm_heap_end();
    return mp_obj_new_int(result);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(run_obj,5,5,run);
static mp_obj_t close_engine(void) {
    scumm_heap_end();scumm_callback=MP_OBJ_NULL;scumm_framebuffer=NULL;return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(close_obj,close_engine);
static mp_obj_t zoom(mp_obj_t value) {
    bool enabled=mp_obj_is_true(value);
    if (enabled!=scumm_zoom) { scumm_zoom=enabled;scumm_zoom_dirty=true; }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(zoom_obj,zoom);
mp_obj_t mpy_init(mp_obj_fun_bc_t *self,size_t n_args,size_t n_kw,mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_run,MP_OBJ_FROM_PTR(&run_obj));
    mp_store_global(MP_QSTR_close,MP_OBJ_FROM_PTR(&close_obj));
    mp_store_global(MP_QSTR_zoom,MP_OBJ_FROM_PTR(&zoom_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
