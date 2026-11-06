"""Host checks for the exact allocator and output routine used by the probe."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('gcc'), 'host GCC required')
class DoomNativeTests(unittest.TestCase):
    def test_arena_and_scanout(self):
        source = (ROOT / 'native/doom/bridge.c').read_text()
        allocator = source[source.index('typedef struct block'):source.index('void *__wrap__malloc_r')]
        renderer = source[source.index('void DG_DrawFrame(void) {'):source.index('char *doom_argv')]
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
uint32_t *DG_ScreenBuffer, *doom_fb;
int gametic, calls, doom_indexed, doom_zoom, doom_zoom_dirty;
unsigned char *I_VideoBuffer;
static int call(int op,int a,int b) {
    assert(op==103 && a==gametic && b==0);calls++;return 0;
}
''' + allocator + renderer + r'''
_Alignas(8) unsigned char arena[4096];
uint32_t source_pixels[320*200/2], output_pixels[480*480/2+8];
static unsigned pixel(unsigned x,unsigned y) {
    const unsigned colours[]={0xf800,0x07e0,0x001f,0xffff,0x1234};
    return colours[(x+y)%5];
}
int main(void) {
    doom_heap=(block *)arena;
    doom_heap->size=sizeof(arena)-sizeof(block);
    doom_heap->next=NULL;doom_heap->free=1;
    void *a=__wrap_malloc(33),*b=__wrap_malloc(65),*c=__wrap_calloc(17,3);
    assert(a && b && c && !((uintptr_t)a&7));
    for(int i=0;i<51;i++)assert(((unsigned char *)c)[i]==0);
    memset(a,123,33);
    void *grown=__wrap_realloc(a,700);assert(grown);
    for(int i=0;i<33;i++)assert(((unsigned char *)grown)[i]==123);
    assert(!__wrap_malloc(SIZE_MAX));assert(!__wrap_calloc(SIZE_MAX,2));
    assert(!__wrap_realloc(b,10000));memset(b,7,65);
    __wrap_free(b);__wrap_free(c);__wrap_free(grown);
    assert(doom_heap->next==NULL && doom_heap->free);
    assert(doom_heap->size==sizeof(arena)-sizeof(block));
    assert(__wrap_malloc(doom_heap->size));assert(!__wrap_malloc(1));

    for(unsigned y=0;y<200;y++)for(unsigned x=0;x<320;x+=2)
        source_pixels[y*160+x/2]=pixel(x,y)|(pixel(x+1,y)<<16);
    for(unsigned i=0;i<sizeof(output_pixels)/4;i++)output_pixels[i]=0xa55aa55a;
    DG_ScreenBuffer=source_pixels;doom_fb=output_pixels+4;
    DG_DrawFrame();assert(calls==1);
    for(unsigned y=0;y<480;y++)for(unsigned x=0;x<480;x++) {
        unsigned expected=0xa55a;
        if(y>=60 && y<420) {
            unsigned p=pixel(x*2/3,(y-60)*5/9);
            expected=((p&255)<<8)|(p>>8);
        }
        unsigned word=doom_fb[y*240+x/2];
        assert(((word>>((x&1)*16))&65535)==expected);
    }
    doom_indexed=1;doom_zoom=1;doom_zoom_dirty=1;
    I_VideoBuffer=(unsigned char *)source_pixels;
    for(unsigned i=0;i<320*200;i++)I_VideoBuffer[i]=(i+i/320)%251;
    for(unsigned i=0;i<sizeof(output_pixels)/4;i++)output_pixels[i]=0xa55aa55a;
    DG_DrawFrame();assert(calls==2);
    const unsigned char *pixels=(const unsigned char *)doom_fb;
    for(unsigned y=0;y<480;y++)for(unsigned x=0;x<480;x++){
        unsigned expected=0;
        if(y>=60&&y<420)expected=I_VideoBuffer[((y-60)*5/9)*320+x*2/3];
        assert(pixels[y*480+x]==expected);
    }
    for(unsigned i=480*480;i<480*480*2;i++)assert(pixels[i]==((i&1)?0xa5:0x5a));
    doom_zoom=0;doom_zoom_dirty=1;DG_DrawFrame();assert(calls==3);
    for(unsigned y=0;y<480;y++)for(unsigned x=0;x<480;x++){
        unsigned expected=0;
        if(y>=140&&y<340&&x>=80&&x<400)expected=I_VideoBuffer[(y-140)*320+x-80];
        assert(pixels[y*480+x]==expected);
    }
    for(unsigned i=0;i<4;i++) {
        assert(output_pixels[i]==0xa55aa55a);
        assert(output_pixels[480*480/2+4+i]==0xa55aa55a);
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'check.c'
            binary = Path(tmp) / 'check'
            src.write_text(program)
            subprocess.run(['gcc', '-O2', '-Wall', '-Wextra', '-fsanitize=undefined',
                            str(src), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
