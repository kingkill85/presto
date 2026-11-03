"""Tiny original test programs, assembled here rather than shipping game ROMs.

These display alternating coloured pixels; they exercise real CPU instructions,
video registers and memory. Kept compatible with MicroPython for device checks.
"""


def gbc_rom():
    rom = bytearray(32768)
    rom[0x100:0x103] = b'\xc3\x50\x01'
    rom[0x143] = 0x80
    code = bytearray(b'\xf3\x31\xf0\xdf\xaf\xe0\x40\x3e\x80\xe0\x68')
    for value in (255, 127, 31, 0, 224, 3, 0, 124):
        code.extend(bytes((0x3e, value, 0xe0, 0x69)))
    code.extend(b'\x21\x00\x80\x06\x10\x3e\xaa\x22\x05\x20\xfc')
    code.extend(b'\x3e\x91\xe0\x40')
    loop = 0x150 + len(code)
    code.extend(bytes((0xc3, loop & 255, loop >> 8)))
    rom[0x150:0x150+len(code)] = code
    rom[0x14d] = (-sum(rom[0x134:0x14d]) - 25) & 255
    return rom


def nes_rom():
    rom = bytearray(16 + 16384 + 8192)
    rom[:6] = b'NES\x1a\x01\x01'
    code = bytearray(b'\x78\xd8\xa2\xff\x9a\xe8\x8e\x00\x20\x8e\x01\x20\x2c\x02\x20')
    code.extend(b'\xa9\x3f\x8d\x06\x20\xa9\x00\x8d\x06\x20')
    for value in (0x0f, 0x30, 0x16, 0x1a):
        code.extend(bytes((0xa9, value, 0x8d, 0x07, 0x20)))
    code.extend(b'\xa9\x00\x8d\x05\x20\x8d\x05\x20\x8d\x06\x20\x8d\x06\x20')
    code.extend(b'\xa9\x0a\x8d\x01\x20')
    loop = 0x8000 + len(code)
    code.extend(bytes((0x4c, loop & 255, loop >> 8)))
    rom[16:16+len(code)] = code
    rom[16+0x3ffa:16+0x4000] = b'\x00\x80\x00\x80\x00\x80'
    rom[16+16384:16+16384+8] = b'\xaa' * 8
    return rom


def sega_rom(gg=False):
    rom = bytearray(32768)
    code = bytearray(b'\xf3\x31\xf0\xdf')

    def out(value, port):
        code.extend(bytes((0x3e, value, 0xd3, port)))

    def reg(index, value):
        out(value, 0xbf)
        out(0x80 | index, 0xbf)

    reg(0, 4)
    reg(1, 0)
    reg(2, 0x0e)
    reg(5, 0x7e)
    out(0, 0xbf)
    out(0x40, 0xbf)
    code.extend(b'\x01\x00\x40\xaf\xd3\xbe\x0b\x78\xb1\x20\xf8')
    out(0, 0xbf)
    out(0x40, 0xbf)
    for value in (0xaa, 0, 0, 0) * 8:
        out(value, 0xbe)
    out(0, 0xbf)
    out(0xc0, 0xbf)
    for value in ((255, 15, 15, 0) if gg else (63, 3)):
        out(value, 0xbe)
    out(0, 0xbf)
    out(0x7f, 0xbf)
    out(0xd0, 0xbe)
    reg(1, 0x40)
    loop = len(code)
    code.extend(bytes((0xc3, loop & 255, loop >> 8)))
    rom[:len(code)] = code
    rom[0x7ff0:0x7ff8] = b'TMR SEGA'
    rom[0x7fff] = 0x6c if gg else 0x4c
    return rom
