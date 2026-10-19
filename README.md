# NES2toCode

A conservative, lossless **iNES/NES 2.0 ROM extraction and reverse-engineering toolkit**, written in Python with a C 6502 execution scaffold.

## Scope

- Preserve and reconstruct every ROM byte, including headers, trainers, PRG, CHR and trailing data.
- Recover static candidate instructions for supported CPU mappings (mappers 0, 2 and 3) and extract graphics as CHR tile sheets.
- Export 6502 candidate instructions and C data/runtime sources. The C probe is **CPU-only**, not a playable NES implementation.
- Preserve raw PRG/CHR for other mappers, including MMC3/mapper 4, without pretending their dynamic CPU bank mapping has been reconstructed.

## Run

```bash
python -m nesrev path/to/your_game.nes --out recovered_game --individual-tiles
python -m unittest discover -s tests -v
```

**Input must be a genuine headered `.nes` binary.** HTML/JavaScript labs are not ROMs, even if they implement browser-side tile inspection. In particular, the supplied `Kunio_Soccer_Original_CHR_Banking_Lab_v0.13.html` initializes `window.__kunioLocalCHRBase64=null`: it does not contain the required CPU ROM image.

## Limitations

ROM machine code does not preserve original C source names or editable project assets. Static disassembly can mistake data for code and cannot establish all banked paths. A graphics tile is not a composed sprite; palettes, OAM, metasprites, animation, runtime CHR decompression and music need separate analysis.

## Tests

14 local automated tests passed (including compiled C diagnostics). Synthetic ROM: three static instruction candidates, 512 CHR tiles, and exact byte-for-byte ROM reconstruction. HTML input: clearly rejected rather than misclassified as NES code.

This repository is for lawful analysis of ROMs you may analyze. Do not publish third-party ROMs or artwork without rights.
