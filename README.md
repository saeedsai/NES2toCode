# NES ROM Reverse Workbench — generic 6502/graphics recovery toolkit

An extensible, **offline**, **Python 3.9+ / standard-library-only** project to analyze a headered Nintendo Entertainment System / Famicom `.nes` ROM. It exports the **entire ROM byte-for-byte** into C arrays and raw sections, discovers plausible 6502 instructions through a conservative control-flow pass, and decodes CHR-ROM into editable tile indices and PNGs. The generated C includes a functioning **CPU-only 6502 diagnostic runtime** (mappers 0, 2, 3), but **not a full NES emulator or complete game decompilation**.

The tool is meant for lawful preservation, interoperability, education, original/homebrew cartridges, and ROMs you have permission to analyze.

## Quick start

From the project folder (no `pip install` required):

```bash
python -m nesrev path/to/your_game.nes --out my_recovered_game --individual-tiles
```

Or install it as a CLI (optional):

```bash
python -m pip install .
nes-reverse path/to/your_game.nes --out my_recovered_game
```

Options:

- `--out <folder>`: output directory (default `<rom_stem>_recovered`).
- `--scale 1|2|3|4|5|6|8`: PNG pixels per CHR pixel, default 2.
- `--individual-tiles`: additionally make one PNG per recovered 8×8 CHR tile (can create thousands of files).

Original, synthetic demo (not a copyrighted commercial ROM):

```bash
python examples/make_demo_rom.py
python -m nesrev examples/synthetic_demo.nes --out demo_output --individual-tiles
```

### Compile and run generated C CPU diagnostic

Inside an exported `c_source/` folder, with a C99 compiler (`cc` / `gcc` / `clang`):

```bash
cc -std=c99 -O2 -Wall -Wextra \
  recovered_data.c recovered_instructions.c lifted_code.c \
  nes_runtime.c probe_main.c -o cpu_probe
./cpu_probe 10000
```

On Windows with MinGW, use `gcc ... -o cpu_probe.exe` then `cpu_probe.exe 10000`.

**Important:** The CPU probe can execute official 6502 instructions in a minimalist memory model; it does not draw a picture, play audio, emulate PPU status/timing, capture controller input, or provide an interactive playable game. Most commercial games cannot progress normally in this CPU-only environment.

## Output file tree

```text
my_recovered_game/
├── manifest.json                   machine-readable header, mapper, hashes, warnings
├── REPORT.md                       summary of recovery and known limitations
├── reconstructed.nes               exact byte-for-byte reassembly (integrity proof)
├── raw/
│   ├── header.bin                  first 16 bytes
│   ├── trainer.bin                 optional 512-byte trainer
│   ├── prg.bin                     every PRG-ROM byte
│   ├── chr.bin                     every CHR-ROM byte, if present
│   ├── trailing.bin                anything after known sections (not thrown away)
│   ├── prg_bank_000.bin            16-KiB physical PRG chunks
│   └── chr_bank_000.bin            8-KiB physical CHR chunks
├── code/
│   ├── bank_000.asm                lossless .byte listing plus inferred opcodes
│   ├── instructions.json           addresses, opcodes, modes, operands
│   └── disassembly.txt             readable candidate 6502 code
├── graphics/
│   ├── chr_bank_000.png            8×8 tile contact sheet, placeholder colors
│   ├── tile_indices_bank_000.json  losslessly editable pixel indices (0..3)
│   ├── bank_000/tile_000.png       only with --individual-tiles
│   └── README.md
└── c_source/
    ├── recovered.h                 header and C IR definitions
    ├── recovered_data.c            complete ROM PRG, CHR, trainer, trailing arrays
    ├── recovered_instructions.c    discovered 6502 instructions as C records
    ├── lifted_code.c               C dispatch table and 151 official opcodes fallback
    ├── nes_runtime.h               CPU and cartridge memory API
    ├── nes_runtime.c               6502 instruction semantics and basic mapper bus
    ├── probe_main.c                bounded CPU-only diagnostic runner
    └── README.md
```

**Integrity:** `reconstructed.nes` is byte-identical to the input (including any unknown trailing bytes). `manifest.json` records both input and reconstructed SHA-256 digests. Each CHR tile's 8×8 2-bit pixel-index array is verified to reconstruct its original 16 bytes. This is *byte recovery*, not a guarantee that the original human-readable game project is recoverable.

## ROM and CPU support

| Feature | Current support | Comments |
|---|---|---|
| Headered `.nes` ROMs | Yes | iNES 1.0 / NES 2.0; includes exponent/multiplier ROM sizes |
| Trainers, PRG, CHR, additional trailing ROM | Yes, lossless | No data bytes are silently discarded |
| 6502 official instruction decoding | All 151 official opcodes | 6502-derived NES CPU; no unofficial opcodes |
| CFG starting from RESET/NMI/IRQ | Mappers 0, 2, 3 | For NROM, UxROM, CNROM cartridge configurations |
| Dynamic bank switching | Mapper 2 PRG / mapper 3 CHR in CPU scaffold | Mapper 2 static analysis explores potential switched banks |
| Other mapper raw extraction | Yes | Code mapping / execution **not modeled** |
| Extract CHR-ROM graphics | Yes | Four-color-index 8×8 tiles, tile sheets, per-tile PNG option |
| Extract graphics on CHR-RAM cartridges | Raw PRG only | Need runtime PPU tracing/decompression to identify these |
| Recover original full source, symbols/functions | No | Compiled ROMs do not contain high-level source metadata |
| Recover full palettes, assembled sprites, backgrounds | No | Runtime PPU registers, palettes, maps, animation needed |
| Decode sound effects, music as MIDI/WAV | No | Runtime APU registers and game-specific sound engines needed |
| Playable HTML / JS / C game | No | Requires full hardware emulation or a verified game-specific rewrite |

### Why complete generic decompilation cannot be guaranteed

- NES programs often mix **6502 instructions and data in the same PRG banks**. A blind linear-sweep disassembler will frequently turn images, text, sprite tables, compressed maps and music into false instructions.
- The game runs with CPU, **PPU (graphics), APU (sound)**, RAM, cartridge **bank switching**, DMA, input, timers and interrupts. ROM bytes alone do not describe their runtime behavior at a high enough level for a fully automated clean-room C game remake.
- Some cartridges store artwork in **CHR-RAM**, building tiles dynamically from compressed PRG data; recovering a screenshot or sprite animation requires following actual graphics writes during execution.
- Original variable names, files, class structures and comments are lost at compilation time. Valid reverse-engineered source necessarily uses inferred names and recovered assembly/IR, not the original Nintendo source files.
- Commercial games may rely on undocumented opcodes, sprite 0 hits, scanline-sensitive effects, undocumented mapper behavior and exact timing, none implemented in this CPU probe.

### Iterative path to a *working* NES-to-C or NES-to-JavaScript converter

1. **Preserve** every original byte and label the ROM hardware accurately (implemented).
2. **Analyze** reachable CPU instructions, and keep all ambiguous bytes as raw data (implemented conservatively).
3. **Trace the actual game in a reference NES emulator**: branch addresses, RAM, mapper writes, PPU updates, APU commands, sound bank usage, controller events. Cross-link traces to ROM offsets (not implemented).
4. **Implement accurate NES hardware/runtime** with CPU, PPU, APU, supported mapper variants, interrupt behavior, sprites and scanline timing; test it against public emulator test ROMs (not implemented).
5. **Lift verified basic blocks into C or JavaScript** with explicit memory/CPU effects, replacing generic dispatch as analysis proves semantics. Add symbolic variables and data structures (not implemented).
6. **Rebuild actual assets** by reconstructing palettes, layout maps, meta-sprites, animation frame sequences, music and compression schemes (not implemented).
7. **Automated differential testing** against the original game on thousands of frames and inputs; compare CPU/RAM/PPU/APU signatures and rendered outputs, then export native or browser packaging (not implemented).

The generated C project intentionally separates the ROM bytes (`recovered_data.c`), disassembly/IR (`recovered_instructions.c`), dispatch (`lifted_code.c`), and runtime (`nes_runtime.c`) so these stages can be developed separately.

## Run regression tests

```bash
python -m unittest discover -s tests -v
```

Tests use only original synthetic data and cover iNES/NES2 headers, malformed ROMs, trainers, exact binary round trips, tile encoding, PNG dimensions, code-flow recovery, mapper-bank contexts, unsupported mapper fallback, and C compilation/execution (if a compiler is installed).

## Source references

- [NESdev: iNES file format](https://www.nesdev.org/wiki/INES)
- [NESdev: NES 2.0 header](https://www.nesdev.org/wiki/NES_2.0)
- [NESdev: PPU pattern tables and 2-bit tiles](https://www.nesdev.org/wiki/PPU_pattern_tables)

## Scope and safety notes

- Only `.nes` (iNES/NES 2.0) is accepted. This project is *not* for SNES `.sfc`, Game Boy `.gb/.gbc`, Nintendo DS `.nds`, FDS, NSF, ZIP, or UNIF formats.
- Output folders are created/updated at the requested path. Choose a new empty output folder if you do not want existing files replaced.
- The program neither accesses the internet nor uploads ROM contents. Extracted output contains the original ROM bytes and should be shared only when permitted.
- This is a recoverer and research scaffold, not a promise of complete automated reproduction for every ROM/memory mapper.

## HTML reconstruction lab input

An `.html` file is **not** an NES ROM. The CLI detects HTML and prints a specific error.
For example, `Kunio_Soccer_Original_CHR_Banking_Lab_v0.13.html` contains
`window.__kunioLocalCHRBase64=null` and uses a local browser file picker; it
does not embed an NES image. To extract original machine code and tiles, provide
the actual headered `.nes` file. Do not rename HTML to `.nes`.

## Current reconstruction scope

The extracted ROM and PRG/CHR blocks are lossless, but disassembled instructions
are conservative candidates and the generated C program is CPU-only. Mapper 4
(MMC3), used by a number of larger games, is currently **raw extraction only**;
its dynamically banked CPU execution cannot be considered converted or verified.
The HTML match simulation is a separate JavaScript prototype, not machine code.
