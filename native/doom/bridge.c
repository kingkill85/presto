// SPDX-License-Identifier: GPL-2.0-or-later
// Doomgeneric adapter with bounded memory saves and cooperative audio. Reset between sessions.
#include "py/dynruntime.h"
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <string.h>

mp_obj_t doom_callback;
uint32_t *doom_fb;
int doom_used, doom_ready, doom_indexed;
int doom_zoom, doom_zoom_dirty;
extern unsigned char *I_VideoBuffer;
unsigned char *doom_save_buffer;
size_t doom_save_pos, doom_save_len, doom_save_limit;
int doom_saving;
extern uint32_t *DG_ScreenBuffer;
extern void doomgeneric_Create(int, char **);
extern void doomgeneric_Tick(void);
extern int gametic;

static void fail(const char *s) { mp_raise_msg(&mp_type_RuntimeError, s); }
static mp_obj_t host(int op, mp_obj_t a, mp_obj_t b) {
    mp_obj_t args[] = {mp_obj_new_int(op), a, b};
    return mp_call_function_n_kw(doom_callback, 3, 0, args);
}
static int call(int op, int a, int b) {
    return mp_obj_get_int(host(op, mp_obj_new_int(a), mp_obj_new_int(b)));
}
// First-fit aligned arena, owned by Python for the entire native session.
// Doom's zone does its own suballocation inside one large arena allocation.
typedef struct block { size_t size; struct block *next; uint32_t free, pad; } block;
block *doom_heap;
// Optional on-chip SRAM, never freed: Doom's hottest buffers avoid the PSRAM cache.
uint8_t *doom_fast;
size_t doom_fast_len, doom_fast_used;
void *doom_fast_alloc(size_t n) {
    size_t start=(doom_fast_used+255)&~(size_t)255;
    if(!doom_fast || start>doom_fast_len || n>doom_fast_len-start) return NULL;
    doom_fast_used=start+n;return doom_fast+start;
}
int doom_is_fast(const void *p) {
    return doom_fast && (const uint8_t *)p>=doom_fast && (const uint8_t *)p<doom_fast+doom_fast_len;
}
void *doom_fast_copy(void *p, size_t n) {
    void *q=doom_fast_alloc(n);if(!q)return p;memcpy(q,p,n);return q;
}
void *__wrap_malloc(size_t n) {
    if (n > SIZE_MAX-7) return NULL;
    n = (n+7)&~7u;
    if (!n) n=8;
    for (block *b=doom_heap;b;b=b->next) if (b->free && b->size>=n) {
        if (b->size>=n+sizeof(block)+8) {
            block *tail=(block *)((uint8_t *)(b+1)+n);
            tail->size=b->size-n-sizeof(block);tail->next=b->next;tail->free=1;
            b->next=tail;b->size=n;
        }
        b->free=0;return b+1;
    }
    return NULL;
}
void __wrap_free(void *p) {
    if (!p) return;
    ((block *)p-1)->free=1;
    for (block *b=doom_heap;b && b->next;) {
        if (b->free && b->next->free) {
            b->size+=sizeof(block)+b->next->size;b->next=b->next->next;
        } else b=b->next;
    }
}
void *__wrap_calloc(size_t n,size_t s) {
    if (s && n>SIZE_MAX/s) return NULL;
    void *p=__wrap_malloc(n*s);if(p) memset(p,0,n*s);return p;
}
void *__wrap_realloc(void *p,size_t n) {
    if (!p) return __wrap_malloc(n);
    if (!n) {__wrap_free(p);return NULL;}
    size_t old=((block *)p-1)->size;
    if(n<=old)return p;
    void *q=__wrap_malloc(n);if(q){memcpy(q,p,old);__wrap_free(p);}return q;
}
void *__wrap__malloc_r(void *r,size_t n){return __wrap_malloc(n);}
void *__wrap__calloc_r(void *r,size_t n,size_t s){return __wrap_calloc(n,s);}
void *__wrap__realloc_r(void *r,void *p,size_t n){return __wrap_realloc(p,n);}
void __wrap__free_r(void *r,void *p){__wrap_free(p);}
int __wrap_printf(const char *fmt,...) {
    va_list a;va_start(a,fmt);int n=mp_vprintf(&mp_plat_print,fmt,a);va_end(a);return n;
}
int __wrap_vfprintf(void *f,const char *fmt,va_list a){return mp_vprintf(&mp_plat_print,fmt,a);}
int __wrap_fprintf(void *f,const char *fmt,...) {
    va_list a;va_start(a,fmt);int n=__wrap_vfprintf(f,fmt,a);va_end(a);return n;
}
int __wrap_puts(const char *s){return mp_printf(&mp_plat_print,"%s\n",s);}
int __wrap_putchar(int c){char s=c;mp_plat_print.print_strn(mp_plat_print.data,&s,1);return c;}
int __wrap_fflush(void *f){return 0;}
void __wrap_exit(int code){fail("Doom engine exited");}
void __wrap__exit(int code){__wrap_exit(code);}
void __wrap_abort(void){fail("Doom engine aborted");}
char *__wrap_getenv(const char *s){return NULL;}
int __wrap_mkdir(const char *s,int mode){return -1;}
int __wrap_remove(const char *s){return -1;}
int __wrap_rename(const char *s,const char *t){return -1;}
int __wrap_system(const char *s){return -1;}
void *__wrap_fopen(const char *p,const char *mode) {
    if (*mode!='r') return NULL;
    return (void *)(uintptr_t)mp_obj_get_int(host(0,mp_obj_new_str(p,strlen(p)),mp_const_none));
}
int __wrap_fclose(void *f){return call(1,(uintptr_t)f,0);}
size_t __wrap_fread(void *p,size_t s,size_t n,void *f) {
    if(!s || n>SIZE_MAX/s)return 0;
    if(f==(void *)(intptr_t)-1) {
        size_t bytes=s*n;
        if(!doom_save_buffer || doom_saving || bytes>doom_save_len-doom_save_pos)fail("Truncated Doom save");
        memcpy(p,doom_save_buffer+doom_save_pos,bytes);doom_save_pos+=bytes;return n;
    }
    int v=mp_obj_get_int(host(2,mp_obj_new_int((uintptr_t)f),mp_obj_new_bytearray_by_ref(s*n,p)));
    return v<0?0:v/s;
}
size_t __wrap_fwrite(const void *p,size_t s,size_t n,void *f){
    if(f!=(void *)(intptr_t)-1)return 0;
    if(!s || n>SIZE_MAX/s)return 0;
    size_t bytes=s*n;
    if(!doom_save_buffer || !doom_saving || bytes>doom_save_limit-doom_save_pos)fail("Doom save too large");
    memcpy(doom_save_buffer+doom_save_pos,p,bytes);doom_save_pos+=bytes;return n;
}
long __wrap_ftell(void *f){if(f==(void *)(intptr_t)-1)return doom_save_pos;return call(3,(uintptr_t)f,0);}
int __wrap_fseek(void *f,long off,int whence) {
    if(whence==1)off+=call(3,(uintptr_t)f,0);
    else if(whence==2)off+=call(4,(uintptr_t)f,0);
    else if(whence!=0)return -1;
    return call(5,(uintptr_t)f,off);
}
int __wrap_fscanf(void *f,const char *fmt,...){return -1;}
int __wrap_feof(void *f){return __wrap_ftell(f)>=call(4,(uintptr_t)f,0);}
int __wrap_ferror(void *f){return 0;}
void *_sbrk(int n){return (void *)-1;}
int _write(int f,const void *p,size_t n){mp_plat_print.print_strn(mp_plat_print.data,p,n);return n;}
int _read(int f,void *p,size_t n){return -1;}
int _close(int f){return -1;}
int _lseek(int f,int p,int w){return -1;}
int _isatty(int f){return 1;}
int _fstat(int f,void *p){return -1;}
int _getpid(void){return 1;}
int _kill(int p,int s){return -1;}
void doom_request_menu(void){call(109,0,0);}
int doom_draw_started,doom_draw_time,doom_draw_tic;
extern int I_GetTime(void);
int doom_drawn_tic;  // gametic+1 of the last rendered tic, 0 before the first
int doom_should_draw(void){
    int now=I_GetTime();
    if(!doom_draw_started){doom_draw_started=1;doom_draw_time=now;doom_draw_tic=gametic;}
    // Nothing changes between tics: never render the same tic twice.
    if(gametic+1==doom_drawn_tic||(now-doom_draw_time)-(gametic-doom_draw_tic)>1)return 0;
    doom_drawn_tic=gametic+1;return 1;
}
void DG_Init(void){}
void DG_SetWindowTitle(const char *s){}
uint32_t DG_GetTicksMs(void){return call(100,0,0);}
void DG_SleepMs(uint32_t ms){call(101,ms,0);}
int DG_GetKey(int *pressed,unsigned char *key) {
    int v=call(102,0,0);if(!v)return 0;
    *pressed=(v>>8)&1;*key=v&255;return 1;
}
void doom_palette(const unsigned char *rgb) {
    if(doom_indexed)host(106,mp_obj_new_bytearray_by_ref(768,(void *)rgb),mp_const_none);
}
void DG_DrawFrame(void) {
    if(doom_indexed) {
        uint8_t *fb=(uint8_t *)doom_fb;
        if(doom_zoom_dirty){memset(fb,0,480*480);doom_zoom_dirty=0;}
        uint32_t row[120];
        for(int y=0;y<200;y++) {
            const uint8_t *src=I_VideoBuffer+y*320;
            if(doom_zoom){
                uint8_t *out=(uint8_t *)row;
                for(int x=0;x<320;x+=2){*out++=src[x];*out++=src[x];*out++=src[x+1];}
                int first=60+(y*9+4)/5,last=60+((y+1)*9+4)/5;
                for(int dy=first;dy<last;dy++){uint32_t *dst=(uint32_t *)(fb+dy*480);for(int x=0;x<120;x++)dst[x]=row[x];}
            }else{
                uint32_t *dst=(uint32_t *)(fb+(y+140)*480+80);
                for(int x=0;x<320;x+=4)*dst++=src[x]|src[x+1]<<8|src[x+2]<<16|(uint32_t)src[x+3]<<24;
            }
        }
        call(103,gametic,0);return;
    }
    // Doom's 320x200 VGA image was displayed at 4:3. Nearest-neighbour
    // 480x360 restores that aspect ratio and uses the full display width.
    // Presto RGB565 stores the high byte first. Pack complete output rows
    // before sequential 32-bit scanout writes; no interleaved halfword stores.
    const uint32_t *src=DG_ScreenBuffer;
    uint32_t row[240];
    for(int y=0;y<200;y++) {
        uint32_t *out=row;
        for(int x=0;x<80;x++) {
            uint32_t ab=*src++,cd=*src++;
            ab=((ab&0x00ff00ff)<<8)|((ab&0xff00ff00)>>8);
            cd=((cd&0x00ff00ff)<<8)|((cd&0xff00ff00)>>8);
            uint32_t a=ab&65535,b=ab>>16,c=cd&65535,d=cd>>16;
            *out++=a|(a<<16);*out++=b|(c<<16);*out++=c|(d<<16);
        }
        int first=60+(y*9+4)/5,last=60+((y+1)*9+4)/5;
        for(int dy=first;dy<last;dy++) {
            uint32_t *dst=doom_fb+dy*240;
            for(int x=0;x<240;x++)dst[x]=row[x];
        }
    }
    call(103,gametic,0);
}

char *doom_argv[20];
static mp_obj_t init(size_t n,const mp_obj_t *args) {
    if(doom_used)fail("Reset before another Doom session");
    mp_buffer_info_t arena,fb;
    mp_get_buffer_raise(args[0],&arena,MP_BUFFER_WRITE);
    mp_get_buffer_raise(args[2],&fb,MP_BUFFER_WRITE);
    if(arena.len<5*1024*1024 || ((uintptr_t)arena.buf&7) || (fb.len!=480*480*2 && fb.len!=480*480) || ((uintptr_t)fb.buf&3))
        mp_raise_ValueError("Doom arena/framebuffer size or alignment");
    if(n>4 && args[4]!=mp_const_none){
        mp_buffer_info_t fast;mp_get_buffer_raise(args[4],&fast,MP_BUFFER_WRITE);
        doom_fast=fast.buf;doom_fast_len=fast.len;doom_fast_used=0;
    }
    doom_indexed=fb.len==480*480;doom_used=1;doom_callback=args[1];doom_fb=fb.buf;
    doom_heap=arena.buf;doom_heap->size=arena.len-sizeof(block);doom_heap->free=1;doom_heap->next=NULL;
    const char *path=mp_obj_str_get_str(args[3]);
    char *copy=__wrap_malloc(strlen(path)+1);memcpy(copy,path,strlen(path)+1);
    const char *av[]={"doom","-iwad",copy,"-mb","4","-nomouse","-nogui","-gfxmode","rgb565","-warp","1","1","-skill","2"};
    for(int i=0;i<14;i++)doom_argv[i]=(char *)av[i];
    doomgeneric_Create(14,doom_argv);
    doom_ready=1;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(init_obj,4,5,init);
static mp_obj_t frame(void){if(!doom_ready)fail("Initialize Doom first");doomgeneric_Tick();return mp_obj_new_int(gametic);}
static MP_DEFINE_CONST_FUN_OBJ_0(frame_obj,frame);
extern void doom_mix(uint32_t *,unsigned,unsigned,unsigned);
extern void doom_archive(void),doom_restore(void),doom_stats(int *);
extern int doom_can_save(void);
static mp_obj_t audio(mp_obj_t buf,mp_obj_t top_obj,mp_obj_t vol_obj){
    mp_buffer_info_t b;mp_get_buffer_raise(buf,&b,MP_BUFFER_WRITE);
    int top=mp_obj_get_int(top_obj),vol=mp_obj_get_int(vol_obj);
    if(b.len!=4096||((uintptr_t)b.buf&3)||top<1||top>65535||vol<0||vol>100)mp_raise_ValueError("Doom audio buffer/range");
    doom_mix(b.buf,1024,top,vol);return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(audio_obj,audio);
static mp_obj_t zoom(mp_obj_t v){doom_zoom=mp_obj_is_true(v);doom_zoom_dirty=1;return mp_const_none;}
static MP_DEFINE_CONST_FUN_OBJ_1(zoom_obj,zoom);
static mp_obj_t redraw(void){doom_zoom_dirty=1;DG_DrawFrame();return mp_const_none;}
static MP_DEFINE_CONST_FUN_OBJ_0(redraw_obj,redraw);
static mp_obj_t capabilities(void){return mp_obj_new_int(doom_ready&&doom_can_save());}
static MP_DEFINE_CONST_FUN_OBJ_0(capabilities_obj,capabilities);
#define STATE_SIZE (256*1024)
static mp_obj_t state_size(void){return mp_obj_new_int(STATE_SIZE);}
static MP_DEFINE_CONST_FUN_OBJ_0(state_size_obj,state_size);
static mp_obj_t save_state(mp_obj_t buf){
    mp_buffer_info_t b;mp_get_buffer_raise(buf,&b,MP_BUFFER_WRITE);
    if(!doom_ready||!doom_can_save()||b.len!=STATE_SIZE)mp_raise_ValueError("Cannot save Doom here");
    memset(b.buf,0,b.len);uint8_t *p=b.buf;memcpy(p,"PD01",4);
    doom_save_buffer=p+8;doom_save_pos=0;doom_save_limit=b.len-8;doom_saving=1;
    doom_archive();unsigned len=doom_save_pos;
    p[4]=len;p[5]=len>>8;p[6]=len>>16;p[7]=len>>24;doom_save_buffer=NULL;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(save_state_obj,save_state);
static mp_obj_t load_state(mp_obj_t buf){
    mp_buffer_info_t b;mp_get_buffer_raise(buf,&b,MP_BUFFER_READ);uint8_t *p=b.buf;
    if(!doom_ready||b.len!=STATE_SIZE||memcmp(p,"PD01",4))mp_raise_ValueError("Invalid Doom save");
    unsigned len=p[4]|p[5]<<8|p[6]<<16|(unsigned)p[7]<<24;
    if(len<50||len>b.len-8||p[8+len-1]!=0x1d||memcmp(p+8+24,"version 109",11)||p[8+40]>4||p[8+41]!=1||p[8+42]<1||p[8+42]>9)mp_raise_ValueError("Invalid Doom save header");
    doom_save_buffer=p+8;doom_save_pos=0;doom_save_len=len;doom_saving=0;
    doom_restore();doom_save_buffer=NULL;doom_zoom_dirty=1;return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(load_state_obj,load_state);
static mp_obj_t fast_used(void){return mp_obj_new_int(doom_fast_used);}
static MP_DEFINE_CONST_FUN_OBJ_0(fast_used_obj,fast_used);
static mp_obj_t status(void){int s[5];doom_stats(s);mp_obj_t out[5];for(int i=0;i<5;i++)out[i]=mp_obj_new_int(s[i]);return mp_obj_new_tuple(5,out);}
static MP_DEFINE_CONST_FUN_OBJ_0(status_obj,status);
extern int doom_weapon_key(void);
static mp_obj_t weapon_key(void){return mp_obj_new_int(doom_weapon_key());}
static MP_DEFINE_CONST_FUN_OBJ_0(weapon_key_obj,weapon_key);
mp_obj_t mpy_init(mp_obj_fun_bc_t *self,size_t n_args,size_t n_kw,mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    doom_zoom=1;doom_zoom_dirty=1;
    mp_store_global(MP_QSTR_init,MP_OBJ_FROM_PTR(&init_obj));
    mp_store_global(MP_QSTR_frame,MP_OBJ_FROM_PTR(&frame_obj));
    mp_store_global(MP_QSTR_audio,MP_OBJ_FROM_PTR(&audio_obj));
    mp_store_global(MP_QSTR_audio_samples,mp_obj_new_int(1024));
    mp_store_global(MP_QSTR_audio_rate,mp_obj_new_int(22050));
    mp_store_global(MP_QSTR_zoom,MP_OBJ_FROM_PTR(&zoom_obj));
    mp_store_global(MP_QSTR_redraw,MP_OBJ_FROM_PTR(&redraw_obj));
    mp_store_global(MP_QSTR_capabilities,MP_OBJ_FROM_PTR(&capabilities_obj));
    mp_store_global(MP_QSTR_state_size,MP_OBJ_FROM_PTR(&state_size_obj));
    mp_store_global(MP_QSTR_save_state,MP_OBJ_FROM_PTR(&save_state_obj));
    mp_store_global(MP_QSTR_load_state,MP_OBJ_FROM_PTR(&load_state_obj));
    mp_store_global(MP_QSTR_weapon_key,MP_OBJ_FROM_PTR(&weapon_key_obj));
    mp_store_global(MP_QSTR_status,MP_OBJ_FROM_PTR(&status_obj));
    mp_store_global(MP_QSTR_fast_used,MP_OBJ_FROM_PTR(&fast_used_obj));
    mp_store_global(MP_QSTR_state_id,mp_obj_new_str("doomgeneric-109-presto-1",sizeof("doomgeneric-109-presto-1")-1));
    MP_DYNRUNTIME_INIT_EXIT
}
