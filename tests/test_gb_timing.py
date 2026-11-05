"""Count emulated clocks across real CPU/HALT/LCD paths, using original code.

A frame must retain scanline overshoot rather than silently discarding cycles.
No commercial ROM or audio reference data is needed for this regression.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
uint64_t clocks;
#define ENABLE_SOUND 0
#define ENABLE_LCD 1
struct gb_s;
#include "core.h"
uint8_t rom[32768];
static uint8_t rr(struct gb_s*g,uint_fast32_t a){return a<sizeof(rom)?rom[a]:255;}
static uint16_t rr16(struct gb_s*g,uint_fast32_t a){return rr(g,a)|(rr(g,a+1)<<8);}
static uint32_t rr32(struct gb_s*g,uint_fast32_t a){return rr16(g,a)|((uint32_t)rr16(g,a+2)<<16);}
static uint8_t cr(struct gb_s*g,uint_fast32_t a){return 255;}
static void cw(struct gb_s*g,uint_fast32_t a,uint8_t v){}
static void err(struct gb_s*g,enum gb_error_e e,uint16_t a){exit(2);}
struct gb_s g;
int main(int argc,char**argv){
 rom[0x100]=0xc3;rom[0x101]=0x50;rom[0x102]=1;
 rom[0x40]=0xd9; // VBlank: RETI
#ifdef COLOR
 rom[0x143]=0x80;
#endif
 unsigned pos=0x150;
 const uint8_t setup[]={0xf3,0x31,0xfe,0xff};
 for(unsigned i=0;i<sizeof(setup);i++)rom[pos++]=setup[i];
 if(argc>1){ // CGB KEY1/STOP double-speed transition
  const uint8_t speed[]={0x3e,1,0xe0,0x4d,0x10,0};
  for(unsigned i=0;i<sizeof(speed);i++)rom[pos++]=speed[i];
 }
 const uint8_t code[]={0xaf,0xe0,0x0f,0x3e,1,0xe0,0xff,0xfb,0x76,0x18,0xfd};
 for(unsigned i=0;i<sizeof(code);i++)rom[pos++]=code[i];
 for(unsigned i=0x134;i<0x14d;i++)rom[0x14d]-=rom[i]+1;
#ifdef COLOR
 int e=gb_init(&g,rr,rr16,rr32,cr,cw,err,NULL);
#else
 int e=gb_init(&g,rr,cr,cw,err,NULL);
#endif
 if(e)return 3;
 gb_init_lcd(&g,NULL);
 for(unsigned i=0;i<10;i++)gb_run_frame(&g);
 uint64_t before=clocks;
 for(unsigned i=0;i<240;i++)gb_run_frame(&g);
 printf("%llu\n",(unsigned long long)(clocks-before));
#ifdef COLOR
 if(argc>1 && !g.cgb.doubleSpeed)return 4;
#endif
}
'''


@unittest.skipUnless(shutil.which('cc'), 'C compiler needed for native timing checks')
class NativeTimingTests(unittest.TestCase):
    def test_scanline_carry_preserves_frame_duration(self):
        for color, path in ((False,'native/gb/peanut_gb.h'),
                            (True,'native/gbc/vendor/walnut_cgb.h')):
            with self.subTest(color=color), tempfile.TemporaryDirectory() as temp:
                folder=Path(temp)
                source=(ROOT/path).read_text()
                elapsed='(inst_cycles >> gb->cgb.doubleSpeed)' if color else 'inst_cycles'
                source=source.replace('/* DIV register timing */',
                                      'clocks += '+elapsed+';\n/* DIV register timing */')
                (folder/'core.h').write_text(source)
                (folder/'check.c').write_text(HARNESS)
                exe=str(folder/'check')
                command=['cc','-O2',str(folder/'check.c'),'-o',exe]
                if color: command.insert(1,'-DCOLOR')
                subprocess.run(command,check=True,capture_output=True,timeout=30)
                for speed in ((False,True) if color else (False,)):
                    result=subprocess.run([exe]+(['double'] if speed else []),
                                          check=True,capture_output=True,text=True,timeout=10)
                    self.assertLessEqual(abs(int(result.stdout)-240*70224),32,
                                         (color,speed,result.stdout))
