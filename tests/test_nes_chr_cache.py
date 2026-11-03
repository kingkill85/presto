"""Exercise the actual C cache with eviction, aliases and writable CHR RAM."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ChrCacheTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'host C compiler required')
    def test_eviction_aliases_and_chr_ram(self):
        source = (ROOT / 'native/nes/vendor/InfoNES.c').read_text()
        start = source.index('static inline BYTE *chr_data(')
        helper = source[start:source.index('\n}', start) + 2]
        cache = source[source.index('BYTE *pbyPrevBank[8];'):]
        program = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t BYTE;
struct { unsigned byVRomSize; } NesHeader;
BYTE ChrBuf[32768], *chr_bank_data[8], *PPUBANK[8], *VROM, ChrBufUpdate;
''' + helper + '\n' + cache + r'''
BYTE rom[65536], ram[8192];
void verify(void) {
  for (unsigned bank=0; bank<8; bank++)
    for (unsigned tile=0; tile<64; tile++)
      for (unsigned y=0; y<8; y++)
        for (unsigned x=0; x<8; x++) {
          BYTE *p=PPUBANK[bank]+tile*16+y;
          unsigned expected=((p[0]>>(7-x))&1)|(((p[8]>>(7-x))&1)<<1);
          assert(*chr_data(ChrBuf+bank*4096+tile*64+y*8+x)==expected);
        }
}
int main(void) {
  for (unsigned i=0;i<sizeof rom;i++) rom[i]=(i*37+(i>>7)*11) ^ (i>>4);
  VROM=rom; NesHeader.byVRomSize=8;
  for(unsigned bank=0;bank<8;bank++) {
    PPUBANK[bank]=rom+bank*1024;
    chr_bank_data[bank]=ChrBuf+bank*4096;
  }
  ChrBufUpdate=255; InfoNES_SetupChr(); verify();
  // Change one bank at a time: unmoved active mappings must survive eviction.
  for(unsigned i=0;i<200;i++) {
    PPUBANK[i%8]=rom+((i*17)%64)*1024;
    InfoNES_SetupChr(); verify();
  }
  PPUBANK[1]=PPUBANK[0]; InfoNES_SetupChr(); verify();
  unsigned decoded=chr_banks;
  for(unsigned i=0;i<10;i++) InfoNES_SetupChr();
  assert(decoded==chr_banks);
  // Switching cartridges clears tags and mapped pointers, as adapter init does.
  memset(chr_cache_tags,0,sizeof chr_cache_tags);
  memset(pbyPrevBank,0,sizeof pbyPrevBank); chr_cache_next=0;
  NesHeader.byVRomSize=0;
  for(unsigned bank=0;bank<8;bank++) {
    PPUBANK[bank]=ram+bank*1024;
    chr_bank_data[bank]=ChrBuf+bank*4096;
  }
  ChrBufUpdate=255; InfoNES_SetupChr(); verify();
  for(unsigned i=0;i<32;i++) {
    unsigned bank=i%8;
    ram[bank*1024+i*7]^=255;
    ChrBufUpdate=1<<bank; InfoNES_SetupChr(); verify();
  }
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'cache.c'
            binary = Path(tmp) / 'cache'
            c.write_text(program)
            subprocess.run(['cc', '-std=c11', '-O2', '-fsanitize=address,undefined',
                            str(c), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)
