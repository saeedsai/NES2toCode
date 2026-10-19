"""Lossless iNES / NES 2.0 cartridge container reader."""
from dataclasses import dataclass
from pathlib import Path
import hashlib

PRG_UNIT = 16384
CHR_UNIT = 8192


@dataclass(frozen=True)
class Cartridge:
    raw: bytes
    header: bytes
    trainer: bytes
    prg: bytes
    chr: bytes
    trailing: bytes
    nes2: bool
    mapper: int
    submapper: int
    mirroring: str
    battery: bool
    prg_ram_bytes: int
    chr_ram_bytes: int

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def prg_banks(self):
        return [self.prg[i:i + PRG_UNIT] for i in range(0, len(self.prg), PRG_UNIT)]

    @property
    def chr_banks(self):
        return [self.chr[i:i + CHR_UNIT] for i in range(0, len(self.chr), CHR_UNIT)]

    @property
    def metadata(self):
        return dict(format='NES 2.0' if self.nes2 else 'iNES 1.0', mapper=self.mapper,
                    submapper=self.submapper, mirroring=self.mirroring, battery=self.battery,
                    trainer_bytes=len(self.trainer), prg_bytes=len(self.prg),
                    chr_bytes=len(self.chr), trailing_bytes=len(self.trailing),
                    prg_ram_bytes=self.prg_ram_bytes, chr_ram_bytes=self.chr_ram_bytes,
                    sha256=self.sha256,
                    warning='Static CPU mapping is reliable only for supported mappers (0, 2, 3).')


def _nes2_size(low, high, unit):
    if high != 15:
        return ((high << 8) | low) * unit
    return (1 << (low >> 2)) * ((low & 3) * 2 + 1)


def _ram_size(nibble):
    return 0 if nibble == 0 else 64 << nibble


def parse_rom(data: bytes) -> Cartridge:
    if len(data) < 16 or data[:4] != b'NES\x1a':
        prefix = data[:512].lstrip().lower()
        if prefix.startswith((b'<!doctype html', b'<html', b'<head', b'<script')):
            raise ValueError('HTML document supplied, not an NES ROM. HTML/JavaScript source is '
                             'not the original 6502 binary. Import or select an actual '
                             'headered .nes ROM (its first four bytes must be 4e 45 53 1a). '
                             'A browser graphics inspector is not a substitute for ROM data.')
        if prefix.startswith(b'pk\x03\x04'):
            raise ValueError('ZIP archive supplied; extract it first and select a .nes ROM.')
        raise ValueError('Not a headered .nes iNES/NES 2.0 ROM (UNIF/FDS/NSF/ZIP unsupported).')
    h = data[:16]
    nes2 = (h[7] & 0x0c) == 0x08
    if nes2:
        prg_size = _nes2_size(h[4], h[9] & 0x0f, PRG_UNIT)
        chr_size = _nes2_size(h[5], h[9] >> 4, CHR_UNIT)
        mapper = (h[6] >> 4) | (h[7] & 0xf0) | ((h[8] & 0x0f) << 8)
        submapper = h[8] >> 4
        prg_ram = _ram_size(h[10] & 0x0f) + _ram_size(h[10] >> 4)
        chr_ram = _ram_size(h[11] & 0x0f) + _ram_size(h[11] >> 4)
    else:
        prg_size = h[4] * PRG_UNIT
        chr_size = h[5] * CHR_UNIT
        # Dirty iNES headers with text in 12..15 frequently corrupt mapper MSB.
        mapper = (h[6] >> 4) | ((h[7] & 0xf0) if h[12:16] == b'\x00'*4 else 0)
        submapper = 0
        prg_ram = (h[8] or 1) * 8192
        chr_ram = 8192 if chr_size == 0 else 0
    trainer_size = 512 if h[6] & 0x04 else 0
    required = 16 + trainer_size + prg_size + chr_size
    if len(data) < required:
        raise ValueError(f'Truncated file: expected at least {required:,} bytes, found {len(data):,}.')
    if not prg_size:
        raise ValueError('ROM has no PRG-ROM; CPU disassembly not supported.')
    if prg_size > 64 * 1024 * 1024 or chr_size > 64 * 1024 * 1024:
        raise ValueError('ROM too large for this safety-limited exporter (64 MiB per section).')
    pos = 16
    trainer = data[pos:pos + trainer_size]
    pos += trainer_size
    prg = data[pos:pos + prg_size]
    pos += prg_size
    chr_data = data[pos:pos + chr_size]
    pos += chr_size
    mirroring = 'four-screen' if h[6] & 0x08 else ('vertical' if h[6] & 1 else 'horizontal')
    return Cartridge(data, h, trainer, prg, chr_data, data[pos:], nes2, mapper, submapper,
                     mirroring, bool(h[6] & 2), prg_ram, chr_ram)


def read_rom(path):
    return parse_rom(Path(path).read_bytes())
