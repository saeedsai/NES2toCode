# NES2toCode — JavaScript/HTML diagnostic milestone (2026-10-19)

## Completed in this increment
- Standalone self-contained `browser/index.html` exporter embedding binary PRG/CHR/trainer data, an official-opcode 6502 JavaScript CPU diagnostic runtime, a register/RAM viewer and raw NES 2bpp CHR tile atlas. No network resources required.
- Separately generated `browser/nes_runtime.js` and `rom_payload.js` for Node.js regression testing.
- JS CPU interpreter handles 151 documented 6502 opcodes for 2A03 CPU semantics (decimal flag does not change ADC/SBC), with 6502 indirect JMP page wrap, stack operations, branches and basic mapper 0/2/3 mapping.
- Explicitly refuses to execute CPU programs on unsupported mappers, including MMC3 (mapper 4). CHR-RAM is identified as having no ROM tiles.
- Added JS CPU, bank-switch, HTML inline-script and browser DOM-stub tests, including test that ROM has 151 supported documented opcodes.
- Switched short C compiler smoke tests to `-O0` to reduce repeated compiler optimization overhead. The CI still performs one optimized `-O2` generated-C probe build.

## Verification performed
- `python -m unittest discover -s tests -v`: 18/18 reported passing locally, consisting of 14 existing and 4 new tests.
- `python -m nesrev examples/synthetic_demo.nes --out demo_output`: exported 512 tiles and reconstructed input byte-exact.
- Node.js running generated `browser/nes_runtime.js` / `rom_payload.js`: after 20 CPU steps, expected A=0x42 and RAM[$0002]=0x42.
- DOM-stub JavaScript evaluation tested inline scripts and a canvas draw, but **not an actual browser engine**.
- Before declaring the GitHub CI green, verify the new post-commit run separately.

## Explicit gaps / blockers
- **Not a playable NES-to-HTML conversion.** Missing NES PPU rasterization/scrolling/sprites, APU sound, DMA, controllers, CPU cycle counting, interrupts, precise mapper hardware behavior, unofficial opcodes, timing and reset behavior beyond the stub.
- Original graphical composition and palette indices require OAM/metasprite and PPU tracing; CHR tiles alone cannot recreate player sprites.
- Dynamic self-modifying code, pointer tables, decompression, runtime code identification and commercial mapper-specific banking are not reconstructed.
- Lacks emulator/differential reference fixture traces, real in-browser testing and complete gameplay validation.
- An HTML/JS research lab attachment is NOT a .nes ROM. Original Kunio Soccer ROM has not been provided for validation in this task.

## Next work
1. Implement a cycle-aware bus/PPU and controller state machine (with validation fixtures).
2. Implement MMC3 PRG/CHR bank mapping and IRQ behavior, using open test ROMs.
3. Add test ROM corpus / reference emulator trace and automated CPU/RAM/PPU/mapper state comparison.
4. Add browser browser-engine smoke tests and rendered image frame hashes, followed by real input regression sequences.
5. Only then evaluate source-lifting and removal of dependency on embedded original ROM bytes.

**Scope:** bit-perfect extraction of ROM is proven for synthetic inputs. Original high-level author source is generally irrecoverable from a ROM and should never be represented as exact output.
