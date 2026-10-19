"""Artifact writer. The raw .nes round-trip is exact, even when analysis is incomplete."""
from pathlib import Path
import hashlib
import json
from .opcodes import OPCODES
from .graphics import iter_tiles, sheet_png, tile_png, encode_tile
from .disasm import Analyzer
from .browser import export_browser


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding='utf-8')
    else:
        path.write_bytes(data)


def c_array(name, data):
    lines = [f'const unsigned char {name}[{len(data)}] = {{']
    for offset in range(0, len(data), 16):
        lines.append('    '+', '.join(f'0x{x:02x}' for x in data[offset:offset+16])+',')
    lines.append('};\n')
    return '\n'.join(lines)


def export_rom(cart, output_dir, scale=2, individual_tiles=False):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    analyzer = Analyzer(cart).analyze()
    raw = out / 'raw'
    _write(raw/'header.bin', cart.header)
    _write(raw/'trainer.bin', cart.trainer)
    _write(raw/'prg.bin', cart.prg)
    _write(raw/'chr.bin', cart.chr)
    _write(raw/'trailing.bin', cart.trailing)
    for i, bank in enumerate(cart.prg_banks):
        _write(raw/f'prg_bank_{i:03d}.bin', bank)
    for i, bank in enumerate(cart.chr_banks):
        _write(raw/f'chr_bank_{i:03d}.bin', bank)
    # The file can always be rebuilt exactly, including trainers and unclassified tail.
    reassembled = cart.header + cart.trainer + cart.prg + cart.chr + cart.trailing
    assert reassembled == cart.raw
    _write(out/'reconstructed.nes', reassembled)

    entries = analyzer.instruction_list()
    by_bank = {}
    for inst in entries:
        by_bank.setdefault(inst.bank, []).append(inst)
    for i, bank in enumerate(cart.prg_banks):
        bank_entries = by_bank.get(i, [])
        header = (f'; PRG bank {i} ({len(bank):,} bytes). Each .byte is authoritative, lossless.\n'
                  '; The recovered instruction comments are HYPOTHESES, not original source.\n'
                  '; This file is an assembler-friendly data listing, not a reconstructed executable.\n')
        rows = [header]
        start = 0x8000 if cart.mapper == 2 or (len(cart.prg_banks) == 2 and i == 0) else 0xC000
        rows.append(f'; Nominal CPU start ${start:04X} (mapper may remap).\n')
        for off in range(0, len(bank), 16):
            b = bank[off:off + 16]
            rows.append(f'; bank offset ${off:04X}\n    .byte '+', '.join(f'${x:02X}' for x in b)+'\n')
        rows.append('\n; Static reachable instruction guesses:\n')
        for inst in bank_entries:
            rows.append(f'; bank+${inst.offset:04X} CPU ${inst.pc:04X} [{inst.raw.hex(" ").upper()}] {inst.text}\n')
        _write(out/'code'/f'bank_{i:03d}.asm', ''.join(rows))
    _write(out/'code'/'instructions.json', json.dumps([e.record for e in entries], indent=2))
    _write(out/'code'/'disassembly.txt', '\n'.join(
        f'BANK {e.bank:03d} +${e.offset:04X} CPU ${e.pc:04X}  {e.raw.hex(" ").upper():<9}  {e.text}'
        for e in entries) + '\n')

    # Portable C blobs preserve 100% of bytes; C instruction IR exposes decoded code.
    c_text = ('/* Generated source data. Not an auto-reconstructed high-level game. */\n'
              '#include "recovered.h"\n\n'
              + c_array('nes_header', cart.header))
    if cart.trainer:
        c_text += c_array('nes_trainer', cart.trainer)
    c_text += c_array('nes_prg_rom', cart.prg)
    if cart.chr:
        c_text += c_array('nes_chr_rom', cart.chr)
    if cart.trailing:
        c_text += c_array('nes_trailing', cart.trailing)
    _write(out/'c_source'/'recovered_data.c', c_text)
    h = ('/* Low-level recovered ROM data and proposed 6502 instructions. */\n'
         '#ifndef NES_RECOVERED_H\n#define NES_RECOVERED_H\n#include <stdint.h>\n#include <stddef.h>\n'
         f'#define NES_MAPPER {cart.mapper}\n'
         f'#define NES_TRAINER_SIZE {len(cart.trainer)}\n'
         'typedef struct {uint16_t pc; uint32_t rom_offset; uint16_t bank; uint8_t opcode; '
         'uint8_t arg0, arg1, width; const char *mnemonic; const char *mode;} NesInstruction;\n'
         'extern const unsigned char nes_header[16];\n'
         f'extern const unsigned char nes_prg_rom[{len(cart.prg)}];\n'
         + (f'extern const unsigned char nes_trainer[{len(cart.trainer)}];\n' if cart.trainer else '')
         + (f'extern const unsigned char nes_chr_rom[{len(cart.chr)}];\n' if cart.chr else '')
         + (f'extern const unsigned char nes_trailing[{len(cart.trailing)}];\n' if cart.trailing else '')
         + 'extern const NesInstruction nes_instructions[];\nextern const size_t nes_instruction_count;\n'
         '#endif\n')
    _write(out/'c_source'/'recovered.h', h)
    ir = ['#include "recovered.h"\n\nconst NesInstruction nes_instructions[] = {\n']
    for e in entries:
        arg0 = e.raw[1] if len(e.raw)>1 else 0
        arg1 = e.raw[2] if len(e.raw)>2 else 0
        ir.append(f'    {{0x{e.pc:04x}, {e.bank*16384+e.offset}, {e.bank}, 0x{e.opcode:02x}, '
                  f'0x{arg0:02x}, 0x{arg1:02x}, {len(e.raw)}, "{e.mnemonic}", "{e.mode}"}},\n')
    # C99 disallows empty inferred arrays, so one sentinel if no code found.
    if not entries:
        ir.append('    {0,0,0,0,0,0,0,"",""},\n')
    ir.append('};\nconst size_t nes_instruction_count = '
              + str(len(entries)) + ';\n')
    _write(out/'c_source'/'recovered_instructions.c', ''.join(ir))
    # Actually lower recovered 6502 control-flow candidates into C opcode dispatch.
    # Instructions not found statically are handled by a dynamic official-opcode decoder.
    dispatch = ['/* Low-level 6502-to-C lifting. Executes CPU instructions only. */\n',
                '#include "nes_runtime.h"\n#include <stdint.h>\n\n',
                'int nes_step_dynamic(NesMachine *m) {\n',
                '  switch (nes_read(m, m->cpu.pc)) {\n']
    for opcode, (op, mode, width) in sorted(OPCODES.items()):
        dispatch.append(f'    case 0x{opcode:02x}: return nes_execute(m, OP_{op}, AM_{mode.upper()});\n')
    dispatch.append('    default: m->halted = 1; return -1;\n  }\n}\n\n')
    dispatch.append('typedef struct {uint32_t off; NesOp op; NesMode mode;} LiftCase;\n')
    dispatch.append('static const LiftCase lifted_cases[] = {\n')
    for e in entries:
        dispatch.append(f'    {{{e.bank*16384+e.offset}, OP_{e.mnemonic}, AM_{e.mode.upper()}}},'
                        f' /* ${e.pc:04x}: {e.text} */\n')
    if not entries:
        dispatch.append('    {0, OP_NOP, AM_IMP}, /* no recovered instructions */\n')
    dispatch.append('};\n\nint nes_lifted_step(NesMachine *m) {\n'
                    '  uint32_t rom_off = nes_rom_offset(m, m->cpu.pc);\n'
                    '  const size_t hi_count='+str(len(entries))+';\n'
                    '  size_t lo=0, hi=hi_count;\n'
                    '  while (lo<hi) {\n'
                    '    size_t mid = lo + (hi-lo)/2;\n'
                    '    if (lifted_cases[mid].off < rom_off) lo = mid+1; else hi = mid;\n'
                    '  }\n'
                    '  if (lo < hi_count && lifted_cases[lo].off == rom_off)\n'
                    '    return nes_execute(m, lifted_cases[lo].op, lifted_cases[lo].mode);\n'
                    '  return nes_step_dynamic(m);\n}\n')
    _write(out/'c_source'/'lifted_code.c', ''.join(dispatch))
    template_dir = Path(__file__).parent/'templates'
    for name in ('nes_runtime.h','nes_runtime.c','probe_main.c'):
        _write(out/'c_source'/name, (template_dir/name).read_bytes())
    _write(out/'c_source'/'README.md',
           '# Generated C code\n\n'
           '`recovered_data.c` preserves all PRG/CHR bytes. `recovered_instructions.c` '
           'lists static, conservative 6502 candidate instructions. '
           '`lifted_code.c` converts those candidates into compact C opcode dispatch records, with a dynamic '
           'official-opcode fallback. `nes_runtime.c` executes official 6502 instructions '
           'and models CPU RAM, cartridge PRG mapping for mappers 0/2/3 and SRAM. '
           'The `probe_main.c` harness runs CPU steps and prints registers.\n\n'
           '**Not a playable game:** This runtime lacks a real PPU renderer, APU sound, '
           'joypad input, DMA, timing, raster IRQ, mapper edge cases, unofficial opcodes, '
           'and game-specific decoding. It does NOT restore the original functions, names, '
           'game design source, music score, sprite animations or tile maps. '
           'It is a low-level CPU analysis scaffold.\n\n'
           'Compile in this folder: `cc -std=c99 -O2 -Wall -Wextra '
           'recovered_data.c recovered_instructions.c lifted_code.c nes_runtime.c '
           'probe_main.c -o cpu_probe`\n'
           'Run: `./cpu_probe 10000`. Only use ROMs you may lawfully analyze.\n')

    export_browser(cart, out/'browser')

    tile_count = 0
    if cart.chr:
        for i, bank in enumerate(cart.chr_banks):
            tiles = list(iter_tiles(bank))
            # NES 2.0 can have a partial CHR bank.
            if tiles:
                # Pixel-index JSON is editable, decodes without any palette, and re-encodes exactly.
                assert b''.join(encode_tile(t) for t in tiles) == bank[:len(tiles)*16]
                _write(out/'graphics'/f'tile_indices_bank_{i:03d}.json',
                       json.dumps(tiles, separators=(',', ':')) + '\n')
                _write(out/'graphics'/f'chr_bank_{i:03d}.png', sheet_png(tiles, scale=scale))
                if individual_tiles:
                    for j, t in enumerate(tiles):
                        _write(out/'graphics'/f'bank_{i:03d}'/f'tile_{j:03d}.png', tile_png(t, scale=scale))
                tile_count += len(tiles)
        _write(out/'graphics'/'README.md',
               '# CHR-ROM tiles\n\nEach NES tile contains 8×8 pixels and four **color indices**, '
               'not final RGB colors. Contact sheets use a placeholder 4-color palette. '
               'The actual game palette, tile maps, animations, OAM sprite placement, flips, '
               'layering, and effects are runtime state and cannot be obtained reliably from CHR-ROM alone.\n\n'
               'The `tile_indices_bank_*.json` files provide editable 8×8 values (0–3) '
               'for each tile, with a verified exact round trip to their 16-byte source.\n')
    else:
        _write(out/'graphics'/'README.md',
               '# CHR-RAM cartridge\n\nThere is no CHR-ROM to extract. The game draws/decompresses '
               'CHR graphics into PPU RAM at runtime (often from PRG-ROM). '
               'Extract those graphics by tracing runtime PPU writes in an emulator.\n')

    if len(cart.chr) % 16:
        analyzer.warnings.append('CHR-ROM contains residual bytes not comprising a full 16-byte tile; raw data preserved.')
    manifest = {**cart.metadata, 'prg_bank_count':len(cart.prg_banks),
                'chr_bank_count':len(cart.chr_banks), 'tile_count':tile_count,
                'static_instruction_count':len(entries), 'entry_points':analyzer.entry_points,
                'warnings':analyzer.warnings,
                'reassembled_sha256':hashlib.sha256(reassembled).hexdigest(),
                'round_trip_exact':reassembled == cart.raw}
    _write(out/'manifest.json', json.dumps(manifest, indent=2)+'\n')
    summary = (f'# Recovery report\n\nSHA-256: `{cart.sha256}`\n\n'
               f'- Mapper/submapper: {cart.mapper}/{cart.submapper}\n'
               f'- PRG-ROM: {len(cart.prg):,} bytes, CHR-ROM: {len(cart.chr):,} bytes\n'
               f'- Static 6502 instruction candidates: {len(entries):,}\n'
               f'- Tiles recovered from CHR-ROM: {tile_count:,}\n'
               f'- ROM reconstructed byte-perfect: {manifest["round_trip_exact"]}\n\n'
               '## Boundaries\n\n\n'+ '\n'.join('- '+s for s in analyzer.warnings)
               + '\n\nAll raw data bytes were preserved, but code and graphics are NOT fully interpreted. '\
               'This tool does not produce a standalone playable game or recover the original source.\n')
    _write(out/'REPORT.md', summary)
    return manifest
