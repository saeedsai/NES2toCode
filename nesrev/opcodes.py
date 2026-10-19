"""Official RP2A03/6502 instruction table, including byte widths and branch behavior."""
MODES = {'imp': 1, 'acc': 1, 'imm': 2, 'zp': 2, 'zpx': 2, 'zpy': 2,
         'ind': 3, 'indx': 2, 'indy': 2, 'abs': 3, 'absx': 3, 'absy': 3, 'rel': 2}
# Mnemonic -> addressing-mode: opcode pairs. All 151 officially documented opcodes.
SPECS = {
'ADC':'imm:69 zp:65 zpx:75 abs:6D absx:7D absy:79 indx:61 indy:71',
'AND':'imm:29 zp:25 zpx:35 abs:2D absx:3D absy:39 indx:21 indy:31',
'ASL':'acc:0A zp:06 zpx:16 abs:0E absx:1E',
'BCC':'rel:90', 'BCS':'rel:B0', 'BEQ':'rel:F0', 'BIT':'zp:24 abs:2C',
'BMI':'rel:30', 'BNE':'rel:D0', 'BPL':'rel:10', 'BRK':'imp:00', 'BVC':'rel:50', 'BVS':'rel:70',
'CLC':'imp:18', 'CLD':'imp:D8', 'CLI':'imp:58', 'CLV':'imp:B8',
'CMP':'imm:C9 zp:C5 zpx:D5 abs:CD absx:DD absy:D9 indx:C1 indy:D1',
'CPX':'imm:E0 zp:E4 abs:EC', 'CPY':'imm:C0 zp:C4 abs:CC',
'DEC':'zp:C6 zpx:D6 abs:CE absx:DE', 'DEX':'imp:CA', 'DEY':'imp:88',
'EOR':'imm:49 zp:45 zpx:55 abs:4D absx:5D absy:59 indx:41 indy:51',
'INC':'zp:E6 zpx:F6 abs:EE absx:FE', 'INX':'imp:E8', 'INY':'imp:C8',
'JMP':'abs:4C ind:6C', 'JSR':'abs:20',
'LDA':'imm:A9 zp:A5 zpx:B5 abs:AD absx:BD absy:B9 indx:A1 indy:B1',
'LDX':'imm:A2 zp:A6 zpy:B6 abs:AE absy:BE',
'LDY':'imm:A0 zp:A4 zpx:B4 abs:AC absx:BC',
'LSR':'acc:4A zp:46 zpx:56 abs:4E absx:5E', 'NOP':'imp:EA',
'ORA':'imm:09 zp:05 zpx:15 abs:0D absx:1D absy:19 indx:01 indy:11',
'PHA':'imp:48', 'PHP':'imp:08', 'PLA':'imp:68', 'PLP':'imp:28',
'ROL':'acc:2A zp:26 zpx:36 abs:2E absx:3E',
'ROR':'acc:6A zp:66 zpx:76 abs:6E absx:7E',
'RTI':'imp:40', 'RTS':'imp:60',
'SBC':'imm:E9 zp:E5 zpx:F5 abs:ED absx:FD absy:F9 indx:E1 indy:F1',
'SEC':'imp:38', 'SED':'imp:F8', 'SEI':'imp:78',
'STA':'zp:85 zpx:95 abs:8D absx:9D absy:99 indx:81 indy:91',
'STX':'zp:86 zpy:96 abs:8E', 'STY':'zp:84 zpx:94 abs:8C',
'TAX':'imp:AA', 'TAY':'imp:A8', 'TSX':'imp:BA', 'TXA':'imp:8A', 'TXS':'imp:9A', 'TYA':'imp:98',
}
OPCODES = {}
for mnemonic, spec in SPECS.items():
    for tok in spec.split():
        mode, byte = tok.split(':')
        num = int(byte, 16)
        assert num not in OPCODES, (mnemonic, num)
        OPCODES[num] = (mnemonic, mode, MODES[mode])
assert len(OPCODES) == 151, len(OPCODES)
BRANCHES = {'BCC','BCS','BEQ','BMI','BNE','BPL','BVC','BVS'}
STOPS = {'RTS', 'RTI', 'BRK'}


def operand_text(mode, operand, pc):
    if mode == 'imp': return ''
    if mode == 'acc': return 'A'
    if mode == 'imm': return '#$%02X' % operand[0]
    if mode == 'rel': return '$%04X' % ((pc + 2 + (operand[0] if operand[0] < 128 else operand[0] - 256)) & 65535)
    val = operand[0] if len(operand) == 1 else operand[0] | (operand[1] << 8)
    symbol = '$%04X' % val if len(operand) == 2 else '$%02X' % val
    return {'zp': symbol, 'zpx': symbol+',X', 'zpy': symbol+',Y',
            'abs': symbol, 'absx': symbol+',X', 'absy': symbol+',Y',
            'ind': '('+symbol+')', 'indx': '('+symbol+',X)', 'indy': '('+symbol+'),Y'}[mode]
