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


def gb_audio_rom(route=0xff, color=False, double_speed=False):
    """Original DMG program: two pulse tones, a wave and LFSR noise.

    route selects NR51 channels for independent mixer checks; 0 is silence.
    No copyrighted sound data or third-party ROM contents.
    """
    rom = bytearray(32768)
    rom[0x100:0x103] = b'\xc3\x50\x01'
    rom[0x143] = 0x80 if color else 0
    code = bytearray(b'\xf3\x31\xf0\xdf')

    def reg(addr, value):
        code.extend(bytes((0x3e, value, 0xe0, addr)))

    if double_speed:
        reg(0x4d, 1)
        # STOP switches CGB speed; a failed switch loops before enabling sound.
        code.extend(b'\x10\x00\xf0\x4d\xe6\x80\x20\x02\x18\xfe')
    reg(0x26, 0x80)
    reg(0x24, 0x77)
    reg(0x25, route)
    reg(0x10, 0)
    for addr, value in ((0x11, 0x80), (0x12, 0xa0), (0x13, 0xd6), (0x14, 0x86),
                        (0x16, 0x40), (0x17, 0x80), (0x18, 0x72), (0x19, 0x86)):
        reg(addr, value)
    reg(0x1a, 0)
    for i in range(16):
        reg(0x30 + i, (i << 4) | (15 - i))
    for addr, value in ((0x1a, 0x80), (0x1b, 0), (0x1c, 0x20),
                        (0x1d, 0x80), (0x1e, 0x87),
                        (0x20, 0), (0x21, 0x40), (0x22, 0x35), (0x23, 0x80)):
        reg(addr, value)
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


def nes_mapper_rom(mapper, chr_ram=None):
    """Original NES program: NMI-driven banking, MMC3 IRQ and CHR-RAM writes.

    Code/vectors are repeated in every 8K PRG bank so mapper writes can select
    real banks without changing the test program. No third-party ROM bytes.
    """
    if mapper not in (0, 1, 2, 3, 4, 7):
        raise ValueError('Unsupported fixture mapper')
    if chr_ram is None:
        chr_ram = mapper in (1, 2, 7)
    if chr_ram and mapper in (3, 4):
        raise ValueError('Unsupported CHR-RAM mapping')
    prg_size, chr_size = 65536, 0 if chr_ram else 32768
    rom = bytearray(16 + prg_size + chr_size)
    rom[:4] = b'NES\x1a'
    rom[4:8] = bytes((4, chr_size//8192, (mapper << 4) | 2, 0))
    code = bytearray(b'\x78\xd8\xa2\xff\x9a\xa9\x00\x85\x00\x85\x01\x85\x02')

    def write(buf, addr, value):
        buf.extend(bytes((0xa9, value, 0x8d, addr & 255, addr >> 8)))

    write(code, 0x2000, 0)
    write(code, 0x2001, 0)
    write(code, 0x4017, 0x40)
    write(code, 0x2006, 0x3f)
    write(code, 0x2006, 0)
    for value in (0x0f, 0x30, 0x16, 0x1a): write(code, 0x2007, value)
    if chr_ram:
        write(code, 0x2006, 0)
        write(code, 0x2006, 0)
        for value in (0xaa,)*8+(0,)*8: write(code, 0x2007, value)
    write(code, 0x2005, 0)
    write(code, 0x2005, 0)
    write(code, 0x2006, 0)
    write(code, 0x2006, 0)
    write(code, 0x2000, 0x80)
    write(code, 0x2001, 0x0a)
    code.append(0x58)  # CLI, allow mapper IRQ
    loop = 0xe000 + len(code)
    code.extend(bytes((0xe6, 2, 0x4c, loop & 255, loop >> 8)))
    assert len(code) < 0x200

    nmi = bytearray(b'\x48\x8a\x48\x98\x48\xe6\x00\xa5\x00\x8d\x00\x60')
    # Exercise serial joypad latch/shift state as well as RAM/SRAM.
    write(nmi, 0x4016, 1); write(nmi, 0x4016, 0)
    nmi.extend(b'\xad\x16\x40\x85\x03')
    if mapper == 1:
        # One bit per frame intentionally leaves partial MMC1 transactions.
        nmi.extend(b'\xa5\x00\x29\x01\x8d\x00\xe0')
    elif mapper in (2, 3):
        nmi.extend(b'\xa5\x00\x29\x03\x8d\x00\x80')
    elif mapper == 4:
        nmi.extend(b'\xa5\x00\x29\x07\x8d\x00\x80')
        nmi.extend(b'\xa5\x00\x29\x0f\x8d\x01\x80')
        nmi.extend(b'\xa5\x00\x29\x01\x8d\x00\xa0')
        write(nmi, 0xc000, 127);write(nmi, 0xc001, 0);write(nmi, 0xe001, 0)
    elif mapper == 7:
        nmi.extend(b'\xa5\x00\x29\x11\x8d\x00\x80')
    if chr_ram:
        write(nmi, 0x2006, 0);write(nmi, 0x2006, 0)
        nmi.extend(b'\xa5\x00\x8d\x07\x20')
        write(nmi, 0x2006, 0);write(nmi, 0x2006, 0)
    nmi.extend(b'\x68\xa8\x68\xaa\x68\x40')
    irq = b'\x48\xa9\x00\x8d\x00\xe0\xe6\x01\x68\x40'
    assert len(nmi) < 0x100
    for bank in range(8):
        base = 16+bank*8192
        rom[base:base+len(code)] = code
        rom[base+0x200:base+0x200+len(nmi)] = nmi
        rom[base+0x300:base+0x300+len(irq)] = irq
        rom[base+0x1ffa:base+0x2000] = b'\x00\xe2\x00\xe0\x00\xe3'
    for bank in range(chr_size//1024):
        base = 16+prg_size+bank*1024
        for row in range(8):
            rom[base+row] = (0xaa,0xcc,0xf0,0x81)[bank%4]
            rom[base+row+8] = (0,0x33,0x0f,0x42)[bank%4]
    return rom
