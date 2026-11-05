"""Build the experimental SCUMM-v4/v5 module against a pinned upstream tree."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--mpy-dir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    root = args.source.resolve()
    revision = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if revision != '949301b6ef87a5482340167378cd102fcdb82ef2':
        raise SystemExit('Unsupported upstream revision; see UPSTREAM.txt')
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True):
        raise SystemExit('Use an unmodified upstream checkout; build transformations live here')
    here = Path(__file__).resolve().parent
    build = here / 'build/engine'
    build.mkdir(parents=True, exist_ok=True)
    cross = os.environ.get('CROSS_COMPILE', 'arm-none-eabi-')
    arch = ['-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard']
    flags = [*arch, '-O2', '-fPIC', '-ffunction-sections', '-fdata-sections',
             '-fno-exceptions', '-fno-rtti', '-fno-threadsafe-statics',
             '-fno-tree-loop-distribute-patterns', '-fno-builtin-malloc',
             '-fno-builtin-calloc', '-fno-builtin-realloc', '-fno-builtin-free',
             '-std=c++17', '-DNDEBUG', '-D__RP2350__=1', '-DENABLE_SCUMM=1',
             '-DCABAL_HAVE_STDINT_H=1', '-DCABAL_LOW_MEMORY=1', '-DDISABLE_GUI=1',
             '-DDISABLE_DEFAULT_AUDIOCD_MANAGER=1', '-DCABAL_MINIMAL_AUDIO=1',
             '-DCABAL_VERSION="presto-experimental"', '-I'+str(root/'src'),
             '-I'+str(root/'src/engines'), '-I'+str(root/'drivers'), '-I'+str(here)]
    cmake = (root/'CMakeLists.txt').read_text()
    sources = []
    for group in ('COMMON','GRAPHICS','GUI','VIDEO','IMAGE','AUDIO','BASE','ENGINE','SCUMM_ENGINE','BACKEND'):
        match = re.search(r'set\('+group+r'_SOURCES\s+(.*?)\n\)', cmake, re.S)
        if match:
            sources.extend(re.findall(r'^\s*(src/\S+\.cpp)', match[1], re.M))
    sources = [root/s for s in dict.fromkeys(sources) if 'platform/rp2350' not in s
               and s not in ('src/base/main.cpp','src/engines/scumm/nut_renderer.cpp',
                             'src/backends/fs/rp2350/rp2350-fs.cpp')]
    system = (root/'src/backends/platform/rp2350/rp2350-system.cpp').read_text()
    system = system.replace('#include "hardware/irq.h"', '').replace('#include "hardware/dma.h"', '')
    # Mixing is cooperative on the engine core. Never touch Presto's
    # DMA interrupts: its display driver owns them.
    system = system.replace('irq_is_enabled(DMA_IRQ_1)', 'false')
    system = system.replace('irq_set_enabled(DMA_IRQ_1, false);', '(void)0;')
    system = system.replace('irq_set_enabled(DMA_IRQ_1, true);', '(void)0;')
    system = system.replace('"/quest/saves"', '"/sd/scumm/saves"')
    system = re.sub(r'^\s*printf\("setMouseCursor[^\n]+\n', '\n', system, flags=re.M)
    system = system.replace('Audio::MixerImpl(this, 44100)', 'Audio::MixerImpl(this, 22050)')
    system += '\nextern "C" void scumm_audio_mix(unsigned char *p, int n) { if (g_mixer) g_mixer->mixCallback(p,n); else memset(p,0,n); }\n'
    system = system.replace('void OSystem_RP2350::updateScreen() {', 'void OSystem_RP2350::updateScreen() {\n scumm_host_call(104,0,0);')
    system = 'extern "C" long scumm_host_call(int,long,long);\n' + system
    # Mixing consumes wall-clock time too. Subtract it from the deadline,
    # rather than adding it to every requested delay and slowing the game.
    system = system.replace('\tcabal_delay(msecs);', r"""
    unsigned start = cabal_get_millis();
    while (msecs) {
        scumm_host_call(104, 0, 0);
        unsigned elapsed = cabal_get_millis() - start;
        if (elapsed >= msecs) break;
        unsigned n = msecs - elapsed;
        cabal_delay(n > 5 ? 5 : n);
        if (_timerManager)
            static_cast<DefaultTimerManager *>(_timerManager)->handler();
    }
""")
    (build/'system.cpp').write_text(system)
    subprocess.run([sys.executable,str(here/'prepare_fs.py'),
                    str(root/'src/backends/fs/rp2350/rp2350-fs.cpp'),str(build/'fs.cpp')],check=True)
    sources += [build/'system.cpp',build/'fs.cpp',here/'engine_entry.cpp']
    flag_file = build/'flags.json'
    compiler_version = subprocess.check_output([cross+'g++','--version'],text=True)
    flag_text = json.dumps([flags,compiler_version,revision])
    flags_changed = not flag_file.exists() or flag_file.read_text() != flag_text

    def compile_one(source):
        obj = build/(str(source).replace('/','_')+'.o')
        # Include changes are covered by rebuilding after changing upstream.
        if not flags_changed and obj.exists() and obj.stat().st_mtime > max(source.stat().st_mtime, (here/'runtime.h').stat().st_mtime):
            return obj, 0
        result = subprocess.run([cross+'g++',*flags,'-c',str(source),'-o',str(obj)],capture_output=True,text=True)
        obj.with_suffix('.log').write_text(result.stdout+result.stderr)
        if result.returncode: print(result.stdout+result.stderr,flush=True)
        return obj,result.returncode
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(compile_one,sources))
    print('Compiled',sum(code==0 for _,code in results),'/',len(results),flush=True)
    if any(code for _,code in results): return 1
    flag_file.write_text(flag_text)
    # The tested fixed-arena allocator is built by the decoder/runtime Makefile.
    allocator = here/'build/dlmalloc.o'
    if not allocator.exists(): raise SystemExit('Build the runtime probe first (make).')
    platform = build/'platform.o'
    subprocess.run([cross+'gcc',*arch,'-O2','-fPIC','-ffunction-sections','-fdata-sections',
                    '-fno-tree-loop-distribute-patterns','-I'+str(root/'src'),
                    '-c',str(here/'engine_platform.c'),'-o',str(platform)],check=True)
    libs = [subprocess.check_output([cross+'gcc',*arch,'-print-file-name='+name],text=True).strip()
            for name in ('libm.a','libc.a','libgcc.a')]
    wraps = ['malloc','calloc','realloc','free','_malloc_r','_calloc_r','_realloc_r','_free_r',
             'printf','puts','fflush','exit','_exit','remove','abort']
    core = build/'core.o'
    subprocess.run([cross+'ld','-r','--gc-sections','-u','scumm_engine_run',
                    '-u','scumm_audio_mix','-u','cabal_update_screen','-u','scumm_engine_state',
                    *[arg for name in ('create_mspace_with_base','destroy_mspace','mspace_malloc',
                        'mspace_calloc','mspace_realloc','mspace_free') for arg in ('-u',name)],
                    '-o',str(core),
                    *('--wrap='+name for name in wraps),*(str(obj) for obj,_ in results),
                    str(allocator),str(platform),'--start-group',*libs,'--end-group'],check=True)
    subprocess.run([cross+'size',str(core)],check=True)
    subprocess.run([sys.executable,str(here/'prepare_data.py'),str(core),str(build/'core_ready.o'),
                    '--ram-bss','--inputs',*(str(obj) for obj,_ in results)],check=True)
    return subprocess.run(['make','-f','Engine.mk','MPY_DIR='+str(args.mpy_dir.resolve()),
                           'SCUMM_DIR='+str(root),'MKDIR=mkdir','RM=rm'],cwd=here).returncode


if __name__ == '__main__':
    sys.exit(main())
