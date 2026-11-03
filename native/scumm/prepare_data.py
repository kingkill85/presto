"""Map initialized C++ data to the native loader's RAM-backed data image.

MicroPython 1.26 persistentcode.c allocates BSS + rodata in writable GC memory
and relocates pointers within it. mpy_ld rejects .data, but supports .data.rel.ro.
Only use this with that loader; a flash-backed loader is NOT compatible.
No constructors are silently discarded: reject .init_array until supported.
"""
import argparse
import os
import subprocess
from elftools.elf.elffile import ELFFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--ram-bss', action='store_true',
                        help='Place zero-initialized engine statics in the same RAM image')
    parser.add_argument('--inputs', nargs='*', default=[],
                        help='Check original objects before section GC can discard constructors')
    args = parser.parse_args()
    for path in args.inputs:
        with open(path, 'rb') as source:
            for section in ELFFile(source).iter_sections():
                if section['sh_size'] and section.name.startswith(
                        ('.init_array', '.ctors', '.fini_array', '.dtors')):
                    raise SystemExit('Explicit constructor/destructor support required: '
                                     + path + ': ' + section.name)
    command = [os.environ.get('CROSS_COMPILE', 'arm-none-eabi-') + 'objcopy', '--strip-unneeded']
    with open(args.source, 'rb') as source:
        elf = ELFFile(source)
        for section in elf.iter_sections():
            name = section.name
            if not section['sh_size']:
                continue
            if name.startswith(('.init_array', '.ctors', '.fini_array', '.dtors')):
                raise SystemExit('Explicit constructor/destructor support required: ' + name)
            if name == '.data' or name.startswith('.data.') and not name.startswith('.data.rel.ro'):
                command += ['--rename-section', name + '=.data.rel.ro.scumm_ram' + name]
            if args.ram_bss and name.startswith('.bss'):
                command += ['--set-section-flags', name+'=alloc,load,data,contents',
                            '--rename-section', name+'=.data.rel.ro.scumm_zero'+name]
    subprocess.run(command + [args.source, args.destination], check=True)


if __name__ == '__main__':
    main()
