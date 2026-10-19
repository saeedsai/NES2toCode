import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from nesrev.rom import parse_rom
from nesrev.disasm import Analyzer
from nesrev.graphics import decode_tile, sheet_png
from nesrev.exporter import export_rom


def make_rom(prg=None, chr_data=None, trainer=None, mapper=0, nes2=False, trailing=b''):
    if prg is None:
        prg = b'\xea' * 16384
    if chr_data is None:
        chr_data = b'\x00' * 8192
    h = bytearray(16)
    h[:4] = b'NES\x1a'
    h[4], h[5] = len(prg)//16384, len(chr_data)//8192
    h[6] = ((mapper & 0x0f) << 4) | (4 if trainer is not None else 0)
    h[7] = mapper & 0xf0
    if nes2:
        h[7] |= 8
    return bytes(h) + (trainer or b'') + bytes(prg) + bytes(chr_data) + trailing


def program_rom(program, init_addr=0xc000, banks=1):
    prg = bytearray(b'\xea' * (banks * 16384))
    base = init_addr - (0x8000 if banks == 2 and init_addr < 0xc000 else 0xc000)
    if banks == 2 and init_addr >= 0xc000:
        base += 16384
    prg[base:base+len(program)] = bytes(program)
    prg[-6:] = bytes([init_addr & 255, init_addr >> 8])*3
    return prg


class ParseTests(unittest.TestCase):
    def test_exact_roundtrip_and_sections(self):
        data = make_rom(trainer=b'Z'*512, trailing=b'END')
        cart = parse_rom(data)
        self.assertEqual(cart.prg, b'\xea'*16384)
        self.assertEqual(cart.trainer, b'Z'*512)
        self.assertEqual(cart.trailing, b'END')
        with tempfile.TemporaryDirectory() as d:
            m = export_rom(cart, d)
            self.assertTrue(m['round_trip_exact'])
            self.assertEqual((Path(d)/'reconstructed.nes').read_bytes(), data)
            self.assertEqual((Path(d)/'raw'/'prg.bin').read_bytes(), cart.prg)
            self.assertIn('NES_MAPPER 0', (Path(d)/'c_source'/'recovered.h').read_text())

    def test_invalid_file_and_truncation(self):
        with self.assertRaises(ValueError):
            parse_rom(b'garbage')
        with self.assertRaises(ValueError):
            parse_rom(b'NES\x1a'+bytes([3,2])+bytes(10))

    def test_nes2_mapper_and_custom_chr_length(self):
        h = bytearray(16)
        h[:4] = b'NES\x1a'
        h[4] = 1
        h[5] = 4 << 2  # exp 4, multiplier 1 => 16 bytes CHR-ROM
        h[6] = 0x20
        h[7] = 0x18  # upper mapper nibble=1 + NES2 flag
        h[8] = 0x32  # submapper 3 and upper mapper bits=2
        h[9] = 0xf0
        raw = bytes(h) + bytes(16384) + bytes(range(16))
        cart = parse_rom(raw)
        self.assertTrue(cart.nes2)
        self.assertEqual(cart.mapper, 0x212)
        self.assertEqual(cart.submapper, 3)
        self.assertEqual(len(cart.chr), 16)
        with tempfile.TemporaryDirectory() as d:
            manifest = export_rom(cart, d)
            self.assertEqual(manifest['tile_count'], 1)
            self.assertEqual(manifest['static_instruction_count'], 0)

    def test_html_is_not_rom(self):
        html = b'<!doctype html><html><script>window.__kunioLocalCHRBase64=null;</script></html>'
        with self.assertRaisesRegex(ValueError, 'HTML document supplied, not an NES ROM'):
            parse_rom(html)
        with self.assertRaisesRegex(ValueError, 'ZIP archive supplied'):
            parse_rom(b'PK\x03\x04' + bytes(20))

    def test_chr_ram_has_no_rom_assets(self):
        data = make_rom(chr_data=b'')
        cart = parse_rom(data)
        with tempfile.TemporaryDirectory() as d:
            meta = export_rom(cart, d)
            self.assertEqual(meta['tile_count'], 0)
            self.assertIn('CHR-RAM', (Path(d)/'graphics'/'README.md').read_text())


class GraphicsTests(unittest.TestCase):
    def test_planes(self):
        # x=0 has index 3; x=7 has index 1
        tile = bytes([0x81]+[0]*7+[0x80]+[0]*7)
        pixels = decode_tile(tile)
        self.assertEqual(pixels[0][0], 3)
        self.assertEqual(pixels[0][7], 1)
        self.assertEqual(pixels[1][0], 0)
        with self.assertRaises(ValueError):
            decode_tile(b'bad')

    def test_png_file_header_and_dimensions(self):
        png = sheet_png([decode_tile(bytes(16))], cols=16, scale=4)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', png[16:24])
        self.assertEqual((width,height), (512,32))


class AnalysisTests(unittest.TestCase):
    def test_reset_flow_and_raw_preservation(self):
        prg = program_rom([0xa9,0x42,0x8d,0x02,0x00,0x4c,0x05,0xc0])
        cart = parse_rom(make_rom(prg=prg))
        analysis = Analyzer(cart).analyze()
        self.assertEqual([e.mnemonic for e in analysis.instruction_list()], ['LDA','STA','JMP'])
        self.assertEqual(analysis.entry_points[1], {'vector':'RESET','cpu_address':0xc000})

    def test_stop_at_invalid_opcode(self):
        prg = program_rom([0x02,0xa9,0x42])
        a = Analyzer(parse_rom(make_rom(prg=prg))).analyze()
        self.assertEqual(len(a.instructions),0)

    def test_uxrom_explores_switchable_banks(self):
        prg = bytearray(b'\xea'*(3*16384))
        prg[0:3] = bytes([0xa9, 0x11, 0x60])  # LDA #11, RTS in bank 0
        prg[16384:16387] = bytes([0xa9, 0x22, 0x60])  # LDA #22, RTS bank 1
        prg[32768:32771] = bytes([0x20,0x00,0x80])  # JSR $8000 in fixed bank
        prg[-6:] = bytes([0x00,0xc0])*3
        a = Analyzer(parse_rom(make_rom(prg=prg,mapper=2))).analyze()
        codes = {(e.bank,e.offset,e.mnemonic) for e in a.instruction_list()}
        self.assertIn((0,0,'LDA'),codes)
        self.assertIn((1,0,'LDA'),codes)
        self.assertIn((2,0,'JSR'),codes)

    def test_unmodeled_mapper_is_lossless(self):
        cart = parse_rom(make_rom(mapper=4))
        a = Analyzer(cart).analyze()
        self.assertFalse(a.supported)
        with tempfile.TemporaryDirectory() as d:
            meta = export_rom(cart,d)
            self.assertEqual(meta['static_instruction_count'],0)
            self.assertTrue(meta['round_trip_exact'])


@unittest.skipUnless(shutil.which('cc'), 'No C compiler available')
class COutputTests(unittest.TestCase):
    def compile_and_run(self, prg, expected, steps=10):
        cart = parse_rom(make_rom(prg=prg))
        with tempfile.TemporaryDirectory() as d:
            export_rom(cart,d)
            cd = Path(d)/'c_source'
            sources = [str(cd/s) for s in ('recovered_data.c','recovered_instructions.c',
                       'lifted_code.c','nes_runtime.c','probe_main.c')]
            exe = Path(d)/'probe'
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                            *sources,'-o',str(exe)], check=True, capture_output=True)
            out = subprocess.run([str(exe),str(steps)], check=True, capture_output=True, text=True).stdout
            self.assertIn(expected,out)

    def test_machine_code_executes(self):
        self.compile_and_run(program_rom([0xa9,0x42,0x8d,0x02,0x00,0x4c,0x05,0xc0]),'RAM[0002]=$42')

    def test_c_branch_and_arithmetic(self):
        # LDA #$7F; CLC; ADC #$01 => A=$80; BPL skip store (not taken); STA $02.
        self.compile_and_run(program_rom([0xa9,0x7f,0x18,0x69,0x01,0x10,0x03,
                                          0x85,0x02,0x4c,0x09,0xc0]),'RAM[0002]=$80',steps=8)

    def test_empty_candidates_compile(self):
        prg = bytearray(b'\xea'*16384)
        prg[-6:] = bytes([0,0])*3
        self.compile_and_run(prg,'CPU reset PC=$0000',steps=0)


if __name__=='__main__':
    unittest.main()
