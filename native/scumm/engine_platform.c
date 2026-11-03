// SPDX-License-Identifier: GPL-2.0-or-later
#include "backends/platform/rp2350/rp2350-minimal.h"
#include "runtime.h"
#include <stdlib.h>
#include <string.h>
extern long scumm_host_call(int op, long a, long b);
uint16_t *scumm_framebuffer;
CabalSurface scumm_screen;
uint8_t scumm_rgb[768];
uint16_t scumm_pens[256];
const uint8_t *scumm_cursor;
int scumm_cw, scumm_ch, scumm_hx, scumm_hy, scumm_mx, scumm_my;
uint8_t scumm_ckey;
bool scumm_cursor_visible, scumm_overlay;
bool scumm_zoom = true;
bool scumm_zoom_dirty;

void cabal_system_init(void) { }
void cabal_init_graphics(int w, int h) {
    if (w != 320 || h != 200) scumm_runtime_fail("Unsupported SCUMM screen size");
    free(scumm_screen.pixels);
    scumm_screen.pixels = calloc(w, h);
    if (!scumm_screen.pixels) scumm_runtime_fail("SCUMM screen allocation failed");
    scumm_screen.width = scumm_screen.pitch = w;
    scumm_screen.height = h;
    scumm_screen.bytesPerPixel = 1;
    memset(scumm_framebuffer, 0, 480 * 480 * 2);
}
CabalSurface *cabal_lock_screen(void) { return &scumm_screen; }
void cabal_unlock_screen(void) { }
void cabal_update_screen(void) {
    if (!scumm_screen.pixels) return;
    if (scumm_zoom_dirty) {
        // Only borders need clearing. The image itself is overwritten below.
        int top = scumm_zoom ? 90 : 140;
        memset(scumm_framebuffer,0,top*480*2);
        memset(scumm_framebuffer+(480-top)*480,0,top*480*2);
        if (!scumm_zoom) {
            for (int y = 140; y < 340; ++y) {
                memset(scumm_framebuffer+y*480,0,80*2);
                memset(scumm_framebuffer+y*480+400,0,80*2);
            }
        }
        scumm_zoom_dirty = false;
    }
    if (scumm_zoom) {
        uint32_t row[240];
        for (int y = 0; y < 200; ++y) {
            const uint8_t *src = scumm_screen.pixels+y*320;
            uint32_t *out = row;
            for (int x = 0; x < 320; x += 4) {
                uint32_t a=scumm_pens[src[x]],b=scumm_pens[src[x+1]];
                uint32_t c=scumm_pens[src[x+2]],d=scumm_pens[src[x+3]];
                *out++=a|(a<<16); *out++=b|(c<<16); *out++=c|(d<<16);
            }
            int dy=90+(y*3+1)/2;
            memcpy(scumm_framebuffer+dy*480,row,sizeof(row));
            if (!(y&1)) memcpy(scumm_framebuffer+(dy+1)*480,row,sizeof(row));
        }
    } else {
        for (int y = 0; y < 200; ++y) {
            uint32_t *out = (uint32_t *)(scumm_framebuffer + (140+y)*480 + 80);
            const uint8_t *row = scumm_screen.pixels + y*320;
            for (int x = 0; x < 320; x += 2)
                *out++ = scumm_pens[row[x]] | ((uint32_t)scumm_pens[row[x+1]] << 16);
        }
    }
    if (scumm_cursor_visible && scumm_cursor) {
        for (int cy = 0; cy < scumm_ch; ++cy) {
            int y = scumm_my - scumm_hy + cy;
            if (y < 0 || y >= 200) continue;
            for (int cx = 0; cx < scumm_cw; ++cx) {
                int x = scumm_mx - scumm_hx + cx;
                uint8_t c = scumm_cursor[cy*scumm_cw+cx];
                if (x >= 0 && x < 320 && c != scumm_ckey) {
                    if (scumm_zoom) {
                        int dx=(x*3+1)/2,dy=90+(y*3+1)/2;
                        for (int yy=0; yy<(y&1?1:2); ++yy)
                            for (int xx=0; xx<(x&1?1:2); ++xx)
                                scumm_framebuffer[(dy+yy)*480+dx+xx]=scumm_pens[c];
                    } else scumm_framebuffer[(140+y)*480+80+x] = scumm_pens[c];
                }
            }
        }
    }
    scumm_host_call(102, 0, 0);
}
void cabal_set_palette(const uint8_t *colors, int start, int num) {
    if (start < 0 || num < 0 || start+num > 256) scumm_runtime_fail("Bad palette range");
    memcpy(scumm_rgb+start*3, colors, num*3);
    for (int i = 0; i < num; ++i) {
        unsigned c = ((colors[0]&248)<<8) | ((colors[1]&252)<<3) | (colors[2]>>3);
        scumm_pens[start+i] = (c>>8) | (c<<8); // Presto RGB565 byte order
        colors += 3;
    }
}
void cabal_get_palette(uint8_t *colors, int start, int num) {
    memcpy(colors, scumm_rgb+start*3, num*3);
}
void cabal_fill_screen(uint8_t color) { memset(scumm_screen.pixels, color, 320*200); }
void cabal_show_overlay(void) { scumm_overlay = true; }
void cabal_hide_overlay(void) { scumm_overlay = false; }
bool cabal_overlay_visible(void) { return scumm_overlay; }
CabalSurface *cabal_get_overlay(void) { return &scumm_screen; }
void cabal_show_mouse(bool visible) { scumm_cursor_visible = visible; }
void cabal_set_mouse_pos(int x, int y) { scumm_mx=x; scumm_my=y; }
void cabal_set_mouse_cursor(const uint8_t *data, int w, int h, int hx, int hy, uint8_t key) {
    scumm_cursor=data; scumm_cw=w; scumm_ch=h; scumm_hx=hx; scumm_hy=hy; scumm_ckey=key;
}
uint32_t cabal_get_millis(void) { return scumm_host_call(100,0,0); }
void cabal_delay(uint32_t ms) { scumm_host_call(101,ms,0); }
int cabal_screen_width(void) { return 320; }
int cabal_screen_height(void) { return 200; }
int frank_quest_cad_consume(void) { return 0; }
