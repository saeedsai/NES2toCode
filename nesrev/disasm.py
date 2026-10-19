"""Conservative 6502 control-flow recovery. Unreachable bytes remain opaque data."""
from collections import deque
from dataclasses import dataclass
from .opcodes import OPCODES, BRANCHES, STOPS, operand_text


@dataclass(frozen=True)
class Instruction:
    bank: int
    offset: int
    pc: int
    opcode: int
    mnemonic: str
    mode: str
    raw: bytes

    @property
    def text(self):
        return self.mnemonic + (' ' + operand_text(self.mode, self.raw[1:], self.pc)
                                if self.mode != 'imp' else '')

    @property
    def record(self):
        return dict(bank=self.bank, bank_offset=self.offset, cpu_address=self.pc,
                    opcode=self.opcode, raw=self.raw.hex(), mnemonic=self.mnemonic,
                    mode=self.mode, asm=self.text)


class Analyzer:
    """Bounded static reachability for common mappers; do not mistake it for ground truth."""
    def __init__(self, cart, max_instructions=300000):
        self.cart = cart
        self.instructions = {}
        self.entry_points = []
        self.warnings = []
        self.max_instructions = max_instructions
        self.supported = (cart.mapper in (0, 2, 3)
                          and len(cart.prg) % 16384 == 0
                          and (cart.mapper == 2 or len(cart.prg_banks) in (1, 2)))
        if not self.supported:
            self.warnings.append(f'Mapper {cart.mapper} PRG CPU mapping not modeled; preserving raw bytes; no CFG recovery.')

    def map_pc(self, pc, low_bank):
        if not self.supported or pc < 0x8000:
            return None
        count = len(self.cart.prg_banks)
        if self.cart.mapper == 2:
            bank = count - 1 if pc >= 0xc000 else low_bank
        elif count == 1:
            bank = 0
        else:
            bank = 1 if pc >= 0xc000 else 0
        return bank, pc & 0x3fff

    def _read_vector(self, location):
        fixed_low = 0
        p0 = self.map_pc(location, fixed_low)
        p1 = self.map_pc(location + 1, fixed_low)
        if p0 is None or p1 is None:
            return None
        b0 = self.cart.prg_banks[p0[0]][p0[1]]
        b1 = self.cart.prg_banks[p1[0]][p1[1]]
        return b0 | (b1 << 8)

    def analyze(self):
        if not self.supported:
            return self
        pending = deque()
        # On bank-switching mapper 2, a jump into $8000-$BFFF is ambiguous.
        # Explore it in every switchable bank, not just whichever happens to be mapped first.
        for vector, name in ((0xfffa, 'NMI'), (0xfffc, 'RESET'), (0xfffe, 'IRQ/BRK')):
            pc = self._read_vector(vector)
            if pc is not None and pc >= 0x8000:
                self.entry_points.append(dict(vector=name, cpu_address=pc))
                if self.cart.mapper == 2 and pc < 0xc000:
                    pending.extend((pc, bank) for bank in range(len(self.cart.prg_banks)-1))
                else:
                    pending.append((pc, 0))
        seen = set()
        while pending and len(seen) < self.max_instructions:
            pc, low_bank = pending.popleft()
            mapping = self.map_pc(pc, low_bank)
            if mapping is None:
                continue
            bank, offset = mapping
            state = (pc, low_bank)
            if state in seen:
                continue
            seen.add(state)
            bank_data = self.cart.prg_banks[bank]
            byte = bank_data[offset]
            info = OPCODES.get(byte)
            if not info:
                continue   # illegal/undocumented opcode or embedded data
            mnemonic, mode, width = info
            if offset + width > len(bank_data):
                continue
            raw = bank_data[offset:offset+width]
            entry = Instruction(bank, offset, pc, byte, mnemonic, mode, raw)
            # Same ROM bytes may be mapped at two mirrored addresses. Preserve first candidate.
            key = (bank, offset)
            prior = self.instructions.get(key)
            if prior and prior.raw != entry.raw:
                self.warnings.append(f'Conflicting interpretation of bank {bank} +${offset:04X}')
            self.instructions.setdefault(key, entry)
            next_pc = (pc + width) & 0xffff
            if mnemonic in STOPS:
                continue
            if mnemonic == 'JMP':
                if mode == 'ind':
                    # Indirect JMP target depends on RAM, not statically knowable.
                    continue
                dest = raw[1] | (raw[2] << 8)
                if self.cart.mapper == 2 and dest < 0xc000 and dest >= 0x8000 and pc >= 0xc000:
                    pending.extend((dest, b) for b in range(len(self.cart.prg_banks)-1))
                else:
                    pending.append((dest, low_bank))
            elif mnemonic == 'JSR':
                dest = raw[1] | (raw[2] << 8)
                if self.cart.mapper == 2 and 0x8000 <= dest < 0xc000 and pc >= 0xc000:
                    pending.extend((dest, b) for b in range(len(self.cart.prg_banks)-1))
                else:
                    pending.append((dest, low_bank))
                pending.append((next_pc, low_bank))
            elif mnemonic in BRANCHES:
                signed = raw[1] - 256 if raw[1] >= 128 else raw[1]
                pending.append(((next_pc + signed) & 0xffff, low_bank))
                pending.append((next_pc, low_bank))
            else:
                pending.append((next_pc, low_bank))
        if pending:
            self.warnings.append('Maximum CFG exploration limit reached; remaining paths omitted.')
        if self.cart.mapper == 2:
            self.warnings.append('UxROM bank switching is dynamic; CFG covers guessed bank contexts, not all executed paths.')
        self.warnings.append('Unreachable bytes might contain code, compressed art, music, maps, tables, or padding.')
        self.warnings.append('Undocumented 6502 opcodes and self-modifying or RAM-executed code are not decoded as instructions.')
        return self

    def instruction_list(self):
        return sorted(self.instructions.values(), key=lambda e: (e.bank, e.offset))
