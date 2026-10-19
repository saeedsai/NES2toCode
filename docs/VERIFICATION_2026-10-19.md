# Verification report — 2026-10-19

## Published revision

Repository: `saeedsai/NES2toCode`, branch `main`.

## User-provided test input

- Filename: `Kunio_Soccer_Original_CHR_Banking_Lab_v0.13.html`
- Size: 155,052 bytes
- SHA-256: `1438a39e08388330031f35cc1e3e6710dedfe26b3ed303e255367fc92224ad4d`
- Identified as HTML/JavaScript, not an iNES/NES 2.0 cartridge.
- No raw `NES\x1a` header was found in the file.
- `window.__kunioLocalCHRBase64=null;` — this lab does not embed the original cartridge's CHR data in that variable.
- Local file selection for optional `.nes`/`.chr` bytes is part of the HTML application.
- **Expected result:** input rejected with explicit HTML-specific diagnostic, exit code 2. It cannot be used to verify conversion of the original game's machine code.

## Code fixes

1. Detect HTML input and provide an actionable error: supply a real headered `.nes` file.
2. Detect ZIP input and advise extraction first.
3. Add an automated regression test for both invalid container types.
4. Document the HTML/input distinction and mapper 4 limitations.
5. Set up GitHub Actions with synthetic ROM reconstruction and generated C probe validation.

## Local regression results

- 14/14 Python tests passed.
- Generated synthetic NES ROM successfully parsed.
- 3 reachable official 6502 instruction candidates detected in synthetic fixture.
- 512 8x8 CHR tiles decoded.
- Rebuilt ROM matches synthetic input byte-for-byte (`cmp`).
- C99 generated CPU probe compiles with `-Wall -Wextra -Werror` and returns `RAM[0002]=$42`.
- HTML input rejected as expected, with no output incorrectly presented as recovered NES code.

## Remote CI

GitHub Actions job `Python and C regression tests` succeeded on commit
`5ee45f014ce87e7b7a0792b7fa131dcb4a808f81`:
https://github.com/saeedsai/NES2toCode/actions/runs/39265622282

## Open limitations

- The attached HTML is not an original ROM. No original Kunio Soccer ROM was available in this test.
- Mapper 4 (MMC3) CPU bank mapping and IRQ behavior are **not** implemented. Raw PRG/CHR extraction is still lossless for mapped ROM containers.
- PPU/APU/controller hardware execution and frame-accurate gameplay are not implemented.
- High-level source functions/names, asset composition, runtime palette and metasprite assemblies, music and compression schemes cannot be reliably restored by static extraction alone.
- Passing synthetic tests does not prove complete conversion of arbitrary game ROMs.
