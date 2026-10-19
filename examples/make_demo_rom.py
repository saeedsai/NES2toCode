"""Build an ORIGINAL, synthetic NES ROM to exercise the recoverer. No game assets."""
from pathlib import Path


def make_demo():
    header = b'NES\x1a' + bytes([1, 1, 0, 0]) + bytes(8)
    prg = bytearray([0xea] * 16384)
    # C000: LDA #$42, STA $0002, JMP $C005 (intentional infinite loop)
    prg[:8] = bytes([0xa9, 0x42, 0x8d, 0x02, 0x00, 0x4c, 0x05, 0xc0])
    for off in (0x3ffa, 0x3ffc, 0x3ffe):
        prg[off:off+2] = bytes([0x00, 0xc0])
    chr_data = bytearray(8192)
    for y in range(8):
        chr_data[y] = 0x81
        chr_data[8+y] = 0xff if y in (0, 7) else 0
    return header + bytes(prg) + bytes(chr_data)


if __name__ == '__main__':
    p = Path(__file__).with_name('synthetic_demo.nes')
    p.write_bytes(make_demo())
    print(f'Created {p}')
