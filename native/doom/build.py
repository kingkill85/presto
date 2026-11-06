"""Build the pinned Doomgeneric Presto module; no game data is bundled."""
import argparse
import os
from pathlib import Path
import re
import subprocess as sp
import sys

REVISION = 'e257a09527062bfb986b6e5e0780839b6cbd5b71'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--mpy-dir', type=Path, required=True)
a = p.parse_args()
root = a.source.resolve()
if sp.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != REVISION:
    raise SystemExit('Wrong Doomgeneric revision; see UPSTREAM.txt')
if sp.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], text=True):
    raise SystemExit('Use an unmodified upstream checkout')
here = Path(__file__).resolve().parent
build = here / 'build'
build.mkdir(exist_ok=True)
source = root / 'doomgeneric'
cross = os.environ.get('CROSS_COMPILE', 'arm-none-eabi-')
arch = ['-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard']
flags = arch + ['-O2', '-fPIC', '-ffunction-sections', '-fdata-sections',
    '-fno-tree-loop-distribute-patterns', '-fno-builtin', '-std=gnu11',
    '-DFEATURE_SOUND=1', '-I'+str(here), '-DDOOMGENERIC_RESX=320', '-DDOOMGENERIC_RESY=200', '-I'+str(source)]
names = re.search(r'^SRC_DOOM = (.*)$', (source/'Makefile').read_text(), re.M)[1].split()
objects = []
for name in names:
    if name == 'doomgeneric_xlib.o':
        continue
    src = source / name.replace('.o', '.c')
    if name == 'i_sound.o':
        text = src.read_text().replace('#include <SDL_mixer.h>', '')
        src = build / 'i_sound.c'
        src.write_text(text)
    elif name == 'd_main.o':
        text = 'int doom_should_draw(void);\n' + src.read_text()
        start = text.index('void doomgeneric_Tick()')
        end = text.index('void D_DoomLoop (void)', start)
        text = text[:start]+text[start:end].replace('if (screenvisible)', 'if (screenvisible && doom_should_draw())')+text[end:]
        src = build / 'd_main.c'
        src.write_text(text)
    elif name == 'd_loop.o':
        text = src.read_text().replace('if (!BuildNewTic())\n        {\n            break;', 'if (!BuildNewTic())\n        {\n            if (!net_client_connected) lasttime -= newtics - i;\n            break;')
        # The wait loop builds the awaited tic just as its one-tic timeout
        # expires, then returned without running it (and D_Display drew the
        # old frame again). Run a tic as soon as it is available.
        wait = '        lowtic = GetLowTic();\n\n\tif (lowtic < gametic/ticdup)'
        if text.count(wait) != 1:
            raise SystemExit('Upstream TryRunTics wait loop changed')
        text = text.replace(wait, '        lowtic = GetLowTic();\n        if (PlayersInGame() && lowtic >= gametic/ticdup + counts)\n            break;\n\n\tif (lowtic < gametic/ticdup)')
        src = build / 'd_loop.c'
        src.write_text(text)
    elif name == 'r_data.o':
        old = 'colormaps = W_CacheLumpNum(lump, PU_STATIC);'
        text = src.read_text()
        if text.count(old) != 1:
            raise SystemExit('Upstream colormap loading changed')
        text = 'void *doom_fast_copy(void *, unsigned);\n' + text.replace(
            old, 'colormaps = doom_fast_copy(W_CacheLumpNum(lump, PU_STATIC), W_LumpLength(lump));')
        src = build / 'r_data.c'
        src.write_text(text)
    elif name == 'p_saveg.o':
        text = src.read_text().replace('saveg_write32((intptr_t) p);', 'saveg_write32(p ? 1 : 0);')
        src = build / 'p_saveg.c'
        src.write_text(text)
    elif name == 'm_menu.o':
        text = 'void doom_request_menu(void);\n' + src.read_text()
        for function in ('M_SaveGame', 'M_LoadGame', 'M_QuitDOOM'):
            match = re.search(r'void\s+'+function+r'\s*\(int choice\)\s*\{', text)
            if not match:
                raise SystemExit('Upstream menu signature changed: '+function)
            start = match.end()
            depth, end = 1, start
            while depth:
                if text[end] == '{': depth += 1
                elif text[end] == '}': depth -= 1
                end += 1
            text = text[:start]+'\n    M_ClearMenus();\n    doom_request_menu();\n'+text[end-1:]
        src = build / 'm_menu.c'
        src.write_text(text)
    elif name == 'i_video.o':
        text = src.read_text()
        text = 'extern int doom_indexed;\nvoid doom_palette(const unsigned char *);\n' + text
        old = 'I_VideoBuffer = (byte*)Z_Malloc (SCREENWIDTH * SCREENHEIGHT, PU_STATIC, NULL);'
        if text.count(old) != 1 or text.count('Z_Free (I_VideoBuffer);') != 1:
            raise SystemExit('Upstream video buffer allocation changed')
        text = 'void *doom_fast_alloc(unsigned);\nint doom_is_fast(const void *);\n' + text
        text = text.replace(old, 'I_VideoBuffer = doom_fast_alloc(SCREENWIDTH * SCREENHEIGHT);\n\tif (!I_VideoBuffer) ' + old)
        text = text.replace('Z_Free (I_VideoBuffer);', 'if (!doom_is_fast(I_VideoBuffer)) Z_Free (I_VideoBuffer);')
        text = text.replace('void I_FinishUpdate (void)\n{', 'void I_FinishUpdate (void)\n{\n    if (doom_indexed) { DG_DrawFrame(); return; }')
        pos = text.index('void I_SetPalette')
        end = text.index('\n}', pos)
        text = text[:end] + '\n    unsigned char rgb[768];\n    for (int j=0;j<256;j++) { rgb[j*3]=colors[j].r; rgb[j*3+1]=colors[j].g; rgb[j*3+2]=colors[j].b; }\n    doom_palette(rgb);' + text[end:]
        src = build / 'i_video.c'
        src.write_text(text)
    obj = build / name
    sp.run([cross+'gcc', *flags, '-c', str(src), '-o', str(obj)], check=True)
    objects.append(str(obj))
for rel in ('sound.c', 'state.c', 'vendor/emu8950.c', 'vendor/emuadpcm.c'):
    obj = build / (Path(rel).stem+'.o')
    sp.run([cross+'gcc', *flags, '-c', str(here/rel), '-o', str(obj)], check=True)
    objects.append(str(obj))
wraps = ('malloc calloc realloc free _malloc_r _calloc_r _realloc_r _free_r '
         'printf fprintf vfprintf puts putchar fflush exit _exit abort '
         'fopen fclose fread fwrite fseek ftell fscanf feof ferror '
         'getenv mkdir remove rename system').split()
libs = [sp.check_output([cross+'gcc', *arch, '-print-file-name='+n],text=True).strip()
        for n in ('libm.a','libc.a','libgcc.a')]
sp.run([cross+'ld', '-r', '--gc-sections', '-u', 'doomgeneric_Create', '-u', 'doomgeneric_Tick',
    '-u', 'doom_mix', '-u', 'doom_archive', '-u', 'doom_restore', '-u', 'doom_can_save', '-u', 'doom_stats', '-u', 'doom_weapon_key', '-o', str(build/'core.o'), *('--wrap='+n for n in wraps), *objects,
    '--start-group', *libs, '--end-group'], check=True)
sp.run([cross+'size', str(build/'core.o')], check=True)
sp.run([sys.executable, str(here/'../scumm/prepare_data.py'), str(build/'core.o'),
        str(build/'core_ready.o'), '--ram-bss', '--inputs', *objects], check=True)
sp.run(['make', 'MPY_DIR='+str(a.mpy_dir.resolve()), 'MKDIR=mkdir', 'RM=rm', 'CROSS='+cross], cwd=here, check=True)
