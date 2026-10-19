# Controller and external-interrupt diagnostic milestone (2026-10-19)

This is a CPU/CHR research workbench, **not** a playable NES-to-HTML conversion.

## Scope
- C/JavaScript controller serial reads at $4016/$4017, strobe/latch, eight ordered button bits per port, then ones.
- HTML diagnostic keyboard and eight touch/pointer buttons for controller 1.
- Manually injected NMI/IRQ: JavaScript requestNMI() and setIRQLine(); C nes_request_nmi() and nes_set_irq_line().
- NMI priority, I-masked level-sensitive IRQ, pushed PC/status with B clear, vector load, RTI restoration.
- The C generated lifted and dynamic dispatch both service pending interrupts before instruction fetch.

## Validation
The integrated local source passed 26/26 automated tests, exact synthetic ROM reconstruction, C and Node.js $42 RAM diagnostics, and real Chromium keyboard/touch smoke. The published revision must pass GitHub CI independently.

## Limitations
No CPU cycle timing, PPU vblank or automatic NMI, APU/MMC3 IRQ generation, DMA, rendering, sound, unofficial opcodes, or real-game parity. An interrupt service counts as one diagnostic step, not seven CPU cycles. Original high-level game source cannot generally be recovered from ROM data.
