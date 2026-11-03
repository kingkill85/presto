"""Compile a SCUMM-v5 constructor dependency graph and check native-module linkage.

This diagnostic intentionally stops at unresolved platform/runtime dependencies.
It does not produce a playable game core or flash firmware.
"""
import argparse
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
    build = Path(__file__).resolve().parent / 'build' / 'audit'
    build.mkdir(parents=True, exist_ok=True)
    cross = os.environ.get('CROSS_COMPILE', 'arm-none-eabi-')
    cmake = (root / 'CMakeLists.txt').read_text()
    groups = ('COMMON', 'GRAPHICS', 'GUI', 'VIDEO', 'IMAGE', 'AUDIO',
              'BASE', 'ENGINE', 'SCUMM_ENGINE', 'BACKEND')
    sources = []
    for group in groups:
        match = re.search(r'set\(' + group + r'_SOURCES\s+(.*?)\n\)', cmake, re.S)
        if match:
            sources.extend(re.findall(r'^\s*(src/\S+\.cpp)', match[1], re.M))
    sources = [s for s in dict.fromkeys(sources) if 'platform/rp2350' not in s
               and s not in ('src/base/main.cpp', 'src/engines/scumm/nut_renderer.cpp')]
    flags = ['-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard',
             '-Os', '-fPIC', '-ffunction-sections', '-fdata-sections', '-fno-exceptions',
             '-fno-builtin-malloc', '-fno-builtin-calloc', '-fno-builtin-realloc', '-fno-builtin-free',
             '-fno-rtti', '-fno-threadsafe-statics', '-fno-tree-loop-distribute-patterns',
             '-std=c++17', '-DNDEBUG', '-D__RP2350__=1', '-DENABLE_SCUMM=1',
             '-DCABAL_HAVE_STDINT_H=1', '-DCABAL_LOW_MEMORY=1', '-DDISABLE_GUI=1',
             '-DDISABLE_DEFAULT_AUDIOCD_MANAGER=1', '-DCABAL_MINIMAL_AUDIO=1',
             '-DCABAL_VERSION="presto-probe"', '-I' + str(root / 'src'),
             '-I' + str(root / 'src/engines'), '-I' + str(root / 'drivers')]

    def compile_one(source):
        obj = build / (source.replace('/', '_') + '.o')
        result = subprocess.run([cross + 'g++', *flags, '-c', str(root / source),
                                 '-o', str(obj)], capture_output=True, text=True)
        obj.with_suffix('.log').write_text(result.stdout + result.stderr)
        return obj, result.returncode

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(compile_one, sources))
    passed = sum(code == 0 for _, code in results)
    print('Compiled %d/%d source files' % (passed, len(sources)), flush=True)
    if passed != len(sources):
        return 1
    entry = build / 'entry.cpp'
    entry.write_text('#include "scumm/scumm_v5.h"\n#include "scumm/detection.h"\n'
                     'extern "C" void *scumm_probe(OSystem *s, const Scumm::DetectorResult *g) {\n'
                     '    return new Scumm::ScummEngine_v5(s, *g);\n}\n')
    subprocess.run([cross + 'g++', *flags, '-c', str(entry), '-o', str(build / 'entry.o')], check=True)
    core = build / 'core.o'
    subprocess.run([cross + 'ld', '-r', '--gc-sections', '-u', 'scumm_probe', '-o', str(core),
                    str(build / 'entry.o'), *(str(obj) for obj, _ in results)], check=True)
    subprocess.run([cross + 'size', str(core)], check=True)
    # Strip unreferenced undefined symbols left behind by ld's section GC;
    # otherwise mpy_ld reports codecs/backends absent from the retained graph.
    ready = build / 'core_ram.o'
    subprocess.run([sys.executable, str(Path(__file__).with_name('prepare_data.py')),
                    str(core), str(ready), '--inputs', str(build / 'entry.o'),
                    *(str(obj) for obj, _ in results)], check=True)
    result = subprocess.run([sys.executable, str(args.mpy_dir / 'tools/mpy_ld.py'),
                             '--arch', 'armv7emsp', '-o', str(build / 'core.mpy'), str(ready)],
                            capture_output=True, text=True)
    (build / 'link.log').write_text(result.stdout + result.stderr)
    print(result.stdout + result.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
