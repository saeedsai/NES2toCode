/* Small CPU-only 2A03 workbench, NOT a playable NES emulator.
   Lacks working PPU, APU, DMA, IRQ timing and controller inputs.
   The real NES 2A03 ignores decimal ADC/SBC (though D flag can be set). */
#include "nes_runtime.h"
#include "recovered.h"
#include <string.h>
#include <limits.h>

#ifndef NES_MAPPER
#error "NES_MAPPER must be defined by generated recovered.h"
#endif
#define F_C 0x01
#define F_Z 0x02
#define F_I 0x04
#define F_D 0x08
#define F_B 0x10
#define F_U 0x20
#define F_V 0x40
#define F_N 0x80

uint32_t nes_rom_offset(const NesMachine *m, uint16_t addr) {
  if (addr < 0x8000) return UINT32_MAX;
  const uint32_t size = sizeof(nes_prg_rom);
  if ((NES_MAPPER == 0 || NES_MAPPER == 3) && (size == 16384 || size == 32768)) {
    return size == 16384 ? ((addr - 0x8000) & 0x3fff) : addr - 0x8000;
  }
  if (NES_MAPPER == 2 && size >= 32768 && size % 16384 == 0) {
    uint32_t count = size / 16384;
    uint32_t bank = addr >= 0xc000 ? count-1 : (m->selected_prg_bank % count);
    return bank * 16384 + (addr & 0x3fff);
  }
  return UINT32_MAX;
}
uint8_t nes_read(NesMachine *m, uint16_t addr) {
  if (addr < 0x2000) return m->ram[addr & 0x07ff];
  if (addr < 0x4000) { m->ppu_accesses++; return 0; } /* PPU stub */
  if (addr < 0x4020) { m->apu_accesses++; return m->io[addr & 0x1f]; }
  if (addr >= 0x6000 && addr < 0x8000) return m->sram[addr - 0x6000];
  if (addr >= 0x8000) {
    uint32_t off = nes_rom_offset(m, addr);
    return off < sizeof(nes_prg_rom) ? nes_prg_rom[off] : 0xff;
  }
  return 0xff;
}
void nes_write(NesMachine *m, uint16_t addr, uint8_t value) {
  if (addr < 0x2000) { m->ram[addr & 0x7ff] = value; return; }
  if (addr < 0x4000) { m->ppu_accesses++; return; } /* PPU stub */
  if (addr < 0x4020) { m->apu_accesses++; m->io[addr & 31] = value; return; }
  if (addr >= 0x6000 && addr < 0x8000) { m->sram[addr - 0x6000] = value; return; }
  if (addr >= 0x8000 && NES_MAPPER == 2) m->selected_prg_bank = value;
  if (addr >= 0x8000 && NES_MAPPER == 3) m->selected_chr_bank = value;
}
int nes_reset(NesMachine *m) {
  memset(m, 0, sizeof(*m));
#if NES_TRAINER_SIZE == 512
  memcpy(&m->sram[0x1000], nes_trainer, 512); /* Trainer maps to CPU $7000-$71FF. */
#endif
  if (nes_rom_offset(m, 0xfffc) == UINT32_MAX) { m->halted = 1; return -1; }
  m->cpu.p = F_I | F_U;
  m->cpu.sp = 0xfd;
  m->cpu.pc = (uint16_t)(nes_read(m, 0xfffc) | ((uint16_t)nes_read(m, 0xfffd)<<8));
  return 0;
}
static uint8_t fetch(NesMachine *m) { return nes_read(m, m->cpu.pc++); }
static uint16_t fetch16(NesMachine *m) {
  uint16_t lo = fetch(m), hi = fetch(m);
  return lo | (hi << 8);
}
static uint16_t zp16(NesMachine *m, uint8_t zp) {
  return nes_read(m, zp) | ((uint16_t)nes_read(m, (uint8_t)(zp+1)) << 8);
}
static uint16_t addr(NesMachine *m, NesMode mode) {
  uint16_t base;
  switch (mode) {
    case AM_IMM: return m->cpu.pc++;
    case AM_ZP: return fetch(m);
    case AM_ZPX: return (uint8_t)(fetch(m) + m->cpu.x);
    case AM_ZPY: return (uint8_t)(fetch(m) + m->cpu.y);
    case AM_ABS: return fetch16(m);
    case AM_ABSX: return (uint16_t)(fetch16(m) + m->cpu.x);
    case AM_ABSY: return (uint16_t)(fetch16(m) + m->cpu.y);
    case AM_INDX: return zp16(m, (uint8_t)(fetch(m) + m->cpu.x));
    case AM_INDY: return (uint16_t)(zp16(m, fetch(m)) + m->cpu.y);
    case AM_IND:
      base = fetch16(m);
      return nes_read(m, base) | ((uint16_t)nes_read(m, (base & 0xff00) | ((base+1) & 0xff)) << 8);
    case AM_REL: { int8_t displacement = (int8_t)fetch(m); return (uint16_t)(m->cpu.pc + displacement); }
    default: return 0;
  }
}
static void flag(NesMachine *m, uint8_t mask, int cond) {
  if (cond) m->cpu.p |= mask;
  else m->cpu.p &= (uint8_t)~mask;
}
static void nz(NesMachine *m, uint8_t v) { flag(m,F_Z,v==0);flag(m,F_N,v&0x80); }
static void push(NesMachine *m, uint8_t value) { nes_write(m, 0x100 | m->cpu.sp--, value); }
static uint8_t pop(NesMachine *m) { return nes_read(m, 0x100 | (uint8_t)(++m->cpu.sp)); }
static void cmp(NesMachine *m, uint8_t a, uint8_t b) { flag(m,F_C,a>=b);nz(m,(uint8_t)(a-b)); }
static void adc(NesMachine *m, uint8_t v) {
  uint8_t a = m->cpu.a;
  unsigned r = (unsigned)a + v + ((m->cpu.p & F_C) != 0);
  flag(m,F_C,r>255);
  flag(m,F_V,(~(a^v) & (a^(uint8_t)r) & 0x80) != 0);
  m->cpu.a = (uint8_t)r; nz(m,m->cpu.a);
}
static void sbc(NesMachine *m, uint8_t v) { adc(m,(uint8_t)~v); }

int nes_execute(NesMachine *m, NesOp op, NesMode mode) {
  if (m->halted) return -1;
  uint16_t oldpc = m->cpu.pc;
  (void)fetch(m); /* Instruction opcode */
  uint16_t ea = addr(m, mode); /* fetches operands according to addressing mode */
  uint8_t v = 0;
  if (mode != AM_IMP && mode != AM_ACC && mode != AM_REL && op != OP_JMP && op != OP_JSR && op != OP_STA && op != OP_STX && op != OP_STY)
    v = nes_read(m, ea);
  uint8_t r;
  switch (op) {
    case OP_ADC: adc(m,v); break;
    case OP_AND: m->cpu.a &= v; nz(m,m->cpu.a); break;
    case OP_ASL:
      r = mode == AM_ACC ? m->cpu.a : v;flag(m,F_C,r&0x80);r<<=1;nz(m,r);
      if(mode==AM_ACC)m->cpu.a=r;else nes_write(m,ea,r);break;
    case OP_BCC: if(!(m->cpu.p&F_C))m->cpu.pc=ea;break;
    case OP_BCS: if(m->cpu.p&F_C)m->cpu.pc=ea;break;
    case OP_BEQ: if(m->cpu.p&F_Z)m->cpu.pc=ea;break;
    case OP_BIT: flag(m,F_Z,(m->cpu.a&v)==0);flag(m,F_N,v&0x80);flag(m,F_V,v&0x40);break;
    case OP_BMI: if(m->cpu.p&F_N)m->cpu.pc=ea;break;
    case OP_BNE: if(!(m->cpu.p&F_Z))m->cpu.pc=ea;break;
    case OP_BPL: if(!(m->cpu.p&F_N))m->cpu.pc=ea;break;
    case OP_BRK:
      m->cpu.pc++;push(m,(uint8_t)(m->cpu.pc>>8));push(m,(uint8_t)m->cpu.pc);
      push(m,m->cpu.p|F_B|F_U);m->cpu.p|=F_I;
      m->cpu.pc=nes_read(m,0xfffe)|((uint16_t)nes_read(m,0xffff)<<8);break;
    case OP_BVC: if(!(m->cpu.p&F_V))m->cpu.pc=ea;break;
    case OP_BVS: if(m->cpu.p&F_V)m->cpu.pc=ea;break;
    case OP_CLC: m->cpu.p &= (uint8_t)~F_C;break;
    case OP_CLD: m->cpu.p &= (uint8_t)~F_D;break;
    case OP_CLI: m->cpu.p &= (uint8_t)~F_I;break;
    case OP_CLV: m->cpu.p &= (uint8_t)~F_V;break;
    case OP_CMP: cmp(m,m->cpu.a,v);break;
    case OP_CPX: cmp(m,m->cpu.x,v);break;
    case OP_CPY: cmp(m,m->cpu.y,v);break;
    case OP_DEC: r=(uint8_t)(v-1);nes_write(m,ea,r);nz(m,r);break;
    case OP_DEX: nz(m,--m->cpu.x);break;
    case OP_DEY: nz(m,--m->cpu.y);break;
    case OP_EOR: m->cpu.a ^=v;nz(m,m->cpu.a);break;
    case OP_INC: r=(uint8_t)(v+1);nes_write(m,ea,r);nz(m,r);break;
    case OP_INX: nz(m,++m->cpu.x);break;
    case OP_INY: nz(m,++m->cpu.y);break;
    case OP_JMP: m->cpu.pc=ea;break;
    case OP_JSR: push(m,(uint8_t)((m->cpu.pc-1)>>8));push(m,(uint8_t)(m->cpu.pc-1));m->cpu.pc=ea;break;
    case OP_LDA: m->cpu.a=v;nz(m,v);break;
    case OP_LDX: m->cpu.x=v;nz(m,v);break;
    case OP_LDY: m->cpu.y=v;nz(m,v);break;
    case OP_LSR:
      r=mode==AM_ACC?m->cpu.a:v;flag(m,F_C,r&1);r>>=1;nz(m,r);
      if(mode==AM_ACC)m->cpu.a=r;else nes_write(m,ea,r);break;
    case OP_NOP: break;
    case OP_ORA: m->cpu.a|=v;nz(m,m->cpu.a);break;
    case OP_PHA: push(m,m->cpu.a);break;
    case OP_PHP: push(m,m->cpu.p|F_B|F_U);break;
    case OP_PLA: m->cpu.a=pop(m);nz(m,m->cpu.a);break;
    case OP_PLP: m->cpu.p=(pop(m)&(uint8_t)~F_B)|F_U;break;
    case OP_ROL:
      r=mode==AM_ACC?m->cpu.a:v;
      { uint8_t carry=(m->cpu.p&F_C)!=0;flag(m,F_C,r&0x80);r=(uint8_t)((r<<1)|carry); }
      nz(m,r);if(mode==AM_ACC)m->cpu.a=r;else nes_write(m,ea,r);break;
    case OP_ROR:
      r=mode==AM_ACC?m->cpu.a:v;
      { uint8_t carry=(m->cpu.p&F_C)!=0;flag(m,F_C,r&1);r=(uint8_t)((r>>1)|(carry<<7)); }
      nz(m,r);if(mode==AM_ACC)m->cpu.a=r;else nes_write(m,ea,r);break;
    case OP_RTI:
      m->cpu.p=(pop(m)&(uint8_t)~F_B)|F_U;
      { uint16_t lo=pop(m);m->cpu.pc=lo|((uint16_t)pop(m)<<8); }break;
    case OP_RTS:
      { uint16_t lo=pop(m);m->cpu.pc=(uint16_t)((lo|((uint16_t)pop(m)<<8))+1); }break;
    case OP_SBC: sbc(m,v);break;
    case OP_SEC: m->cpu.p|=F_C;break;
    case OP_SED: m->cpu.p|=F_D;break;
    case OP_SEI: m->cpu.p|=F_I;break;
    case OP_STA: nes_write(m,ea,m->cpu.a);break;
    case OP_STX: nes_write(m,ea,m->cpu.x);break;
    case OP_STY: nes_write(m,ea,m->cpu.y);break;
    case OP_TAX: m->cpu.x=m->cpu.a;nz(m,m->cpu.x);break;
    case OP_TAY: m->cpu.y=m->cpu.a;nz(m,m->cpu.y);break;
    case OP_TSX: m->cpu.x=m->cpu.sp;nz(m,m->cpu.x);break;
    case OP_TXA: m->cpu.a=m->cpu.x;nz(m,m->cpu.a);break;
    case OP_TXS: m->cpu.sp=m->cpu.x;break;
    case OP_TYA: m->cpu.a=m->cpu.y;nz(m,m->cpu.a);break;
    default: m->halted=1;return -1;
  }
  (void)oldpc;
  m->cpu.p |= F_U;
  m->steps++;
  return 0;
}
