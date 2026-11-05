// Original synthetic renderer fixture; no game data.
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "backends/platform/rp2350/rp2350-minimal.h"
extern uint16_t *scumm_framebuffer;
extern uint16_t scumm_pens[256];
extern bool scumm_zoom, scumm_zoom_dirty, scumm_indexed;
void scumm_host_palette(const uint8_t *rgb) { (void)rgb; }
static unsigned presentations;
long scumm_host_call(int op,long a,long b) {
    assert(op==102);(void)a;(void)b;++presentations;return 0;
}
void scumm_runtime_fail(const char *message) { puts(message);abort(); }

static void check_format(bool indexed) {
    scumm_indexed=indexed;
    size_t bytes=480*480*(indexed?1:2);
    uint8_t *allocation=malloc(bytes+32);
    assert(allocation);
    for (unsigned i=0;i<bytes+32;++i) allocation[i]=0x5a;
    scumm_framebuffer=(uint16_t *)(allocation+16);
    cabal_init_graphics(320,200);
    uint8_t *pixels=cabal_lock_screen()->pixels;
    for (unsigned i=0;i<320*200;++i) pixels[i]=(i*7+i/320)%256;
    for (unsigned i=0;i<256;++i) scumm_pens[i]=i+1;
    for (unsigned mode=0;mode<4;++mode) {
        scumm_zoom=mode&1;
        scumm_zoom_dirty=true;
        cabal_update_screen();
        for (unsigned y=0;y<480;++y) for (unsigned x=0;x<480;++x) {
            uint16_t expected=0;
            if (scumm_zoom) {
                if (y>=90 && y<390) expected=indexed ? pixels[((y-90)*2/3)*320+x*2/3] : scumm_pens[pixels[((y-90)*2/3)*320+x*2/3]];
            } else if (y>=140 && y<340 && x>=80 && x<400) {
                expected=indexed ? pixels[(y-140)*320+x-80] : scumm_pens[pixels[(y-140)*320+x-80]];
            }
            assert((indexed ? ((uint8_t *)scumm_framebuffer)[y*480+x] : scumm_framebuffer[y*480+x])==expected);
        }
    }
    uint8_t cursor[]={1,2,3,255};
    cabal_show_mouse(true);
    cabal_set_mouse_cursor(cursor,2,2,1,1,255);
    for (int mode=0;mode<2;++mode) {
        scumm_zoom=mode;scumm_zoom_dirty=true;
        for (int corner=0;corner<4;++corner) {
            cabal_set_mouse_pos(corner&1?320:0,corner&2?200:0);
            cabal_update_screen();
            for (int i=0;i<16;++i) {
                assert(allocation[i]==0x5a);
                assert(allocation[bytes+16+i]==0x5a);
            }
        }
    }
    cabal_show_mouse(false);
    free(pixels);cabal_lock_screen()->pixels=NULL;free(allocation);
}

int main(void) {
    check_format(false);
    check_format(true);
    assert(presentations==24);
    puts("PASS SCUMM renderer: exact pixels, zoom switching, borders and clipped cursor");
    return 0;
}
