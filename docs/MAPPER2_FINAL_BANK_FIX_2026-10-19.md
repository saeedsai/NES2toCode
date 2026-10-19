# Mapper 2 final-bank selection — 2026-10-19

Fixed the C and JavaScript CPU workbench's UxROM bank selection. The switchable $8000–$BFFF window can now select the final physical PRG bank (previously modulo bank_count - 1 excluded it), while $C000–$FFFF stays fixed to the final bank. Static CFG exploration now also considers the final bank in the lower window.

Two new committed regression tests check mapper 2 final-bank reads in JavaScript/Node and C99. The committed suite contains 20 tests (18 baseline plus 2 new). A separate local test of static CFG discovery also passed but is not included in this commit.

Scope: CPU-level bank selection for a simplified mapper 2 model. Board-specific bank masks, bus conflicts, NES PPU/APU, and real-game parity remain unverified.
