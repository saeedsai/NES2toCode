/* Debug-only CPU harness. Does not render graphics or play sound. */
#include "nes_runtime.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
  NesMachine m;
  unsigned long limit = 5000;
  if (argc > 1) limit = strtoul(argv[1], 0, 0);
  if (limit > 1000000UL) { fputs("Max 1000000 CPU steps\n", stderr); return 2; }
  if (nes_reset(&m) != 0) {
    fputs("Unsupported CPU ROM layout for this mapper.\n", stderr); return 2;
  }
  printf("CPU reset PC=$%04X\n", m.cpu.pc);
  for (unsigned long i=0; i<limit; ++i) {
    if (nes_lifted_step(&m) != 0) {
      fprintf(stderr,"Stopped at PC=$%04X (unknown/undocumented opcode)\n",m.cpu.pc);
      break;
    }
  }
  printf("CPU PC=$%04X A=$%02X X=$%02X Y=$%02X SP=$%02X P=$%02X steps=%llu\n",
         m.cpu.pc,m.cpu.a,m.cpu.x,m.cpu.y,m.cpu.sp,m.cpu.p,
         (unsigned long long)m.steps);
  printf("RAM[0002]=$%02X PPU_stub_accesses=%u APU_IO_stub_accesses=%u\n",
         m.ram[2], m.ppu_accesses, m.apu_accesses);
  puts("Warning: CPU-only diagnostic; not an NES emulator or a playable converted game.");
  return 0;
}
