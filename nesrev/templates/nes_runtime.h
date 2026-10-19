#ifndef NES_RUNTIME_H
#define NES_RUNTIME_H
#include <stdint.h>
#include <stddef.h>

typedef enum {
  OP_ADC,OP_AND,OP_ASL,OP_BCC,OP_BCS,OP_BEQ,OP_BIT,OP_BMI,OP_BNE,OP_BPL,
  OP_BRK,OP_BVC,OP_BVS,OP_CLC,OP_CLD,OP_CLI,OP_CLV,OP_CMP,OP_CPX,OP_CPY,
  OP_DEC,OP_DEX,OP_DEY,OP_EOR,OP_INC,OP_INX,OP_INY,OP_JMP,OP_JSR,OP_LDA,
  OP_LDX,OP_LDY,OP_LSR,OP_NOP,OP_ORA,OP_PHA,OP_PHP,OP_PLA,OP_PLP,OP_ROL,
  OP_ROR,OP_RTI,OP_RTS,OP_SBC,OP_SEC,OP_SED,OP_SEI,OP_STA,OP_STX,OP_STY,
  OP_TAX,OP_TAY,OP_TSX,OP_TXA,OP_TXS,OP_TYA
} NesOp;
typedef enum {
  AM_IMP,AM_ACC,AM_IMM,AM_ZP,AM_ZPX,AM_ZPY,AM_IND,
  AM_INDX,AM_INDY,AM_ABS,AM_ABSX,AM_ABSY,AM_REL
} NesMode;
typedef struct {
  uint16_t pc;
  uint8_t a,x,y,sp,p;
} NesRegisters;
typedef struct {
  NesRegisters cpu;
  uint8_t ram[2048], sram[8192], io[32];
  uint8_t selected_prg_bank, selected_chr_bank;
  uint8_t controller_buttons[2], controller_shift[2], controller_reads[2], controller_strobe;
  uint64_t steps;
  unsigned ppu_accesses, apu_accesses;
  int halted;
  uint8_t nmi_pending, irq_line;
} NesMachine;

void nes_set_controller(NesMachine *m, unsigned port, uint8_t buttons);
void nes_request_nmi(NesMachine *m);
void nes_set_irq_line(NesMachine *m, int asserted);
/* Returns 1 when an interrupt is serviced; zero otherwise. */
int nes_service_interrupt(NesMachine *m);
uint32_t nes_rom_offset(const NesMachine *m, uint16_t address);
uint8_t nes_read(NesMachine *m, uint16_t address);
void nes_write(NesMachine *m, uint16_t address, uint8_t value);
int nes_reset(NesMachine *m);
int nes_execute(NesMachine *m, NesOp opcode, NesMode mode);
int nes_step_dynamic(NesMachine *m);
int nes_lifted_step(NesMachine *m);
#endif
