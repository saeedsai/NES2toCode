"""External NMI/IRQ CPU-hook tests using a synthetic mapper-0 ROM."""
import json, shutil, subprocess, tempfile, unittest
from pathlib import Path
from nesrev.rom import parse_rom
from nesrev.browser import export_browser
from nesrev.exporter import export_rom

def fixture():
    prg=bytearray([0xea]*16384)
    prg[:5]=bytes([0x58,0xea,0x4c,0x01,0xc0])
    prg[0x100:0x105]=bytes([0xa9,0x31,0x85,0x03,0x40])
    prg[0x110:0x115]=bytes([0xa9,0x42,0x85,0x04,0x40])
    prg[-6:]=bytes([0,0xc1,0,0xc0,0x10,0xc1])
    h=bytearray(16);h[:4]=bytes([78,69,83,26]);h[4]=1
    return parse_rom(bytes(h)+prg)

class InterruptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_js_nmi_preempts_irq_and_rti_restores_pc(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_browser(fixture(),out)
            js="""require(process.argv[1]+'/rom_payload.js');
            const m=new (require(process.argv[1]+'/nes_runtime.js').Machine)(globalThis.NES_PAYLOAD);
            m.setIRQLine(true);m.step();const cli=m.pc;
            m.step();const irq={pc:m.pc,sp:m.sp,hi:m.ram[0x1fd],lo:m.ram[0x1fc],p:m.ram[0x1fb]};
            m.requestNMI();m.step();const nmi={pc:m.pc,sp:m.sp,p:m.ram[0x1f8]};
            m.step();m.step();m.step();const afterNmi=m.pc;m.setIRQLine(false);
            m.step();m.step();m.step();m.step();
            console.log(JSON.stringify({cli,irq,nmi,afterNmi,pc:m.pc,sp:m.sp,steps:m.steps,ram3:m.ram[3],ram4:m.ram[4]}));"""
            r=subprocess.run(['node','-e',js,str(out)],capture_output=True,text=True,check=True)
            d=json.loads(r.stdout)
            self.assertEqual(d['cli'],0xc001)
            self.assertEqual((d['irq']['pc'],d['irq']['sp'],d['irq']['hi'],d['irq']['lo']),(0xc110,0xfa,0xc0,1))
            self.assertEqual(d['irq']['p']&0x30,0x20)
            self.assertEqual((d['nmi']['pc'],d['nmi']['sp'],d['nmi']['p']&0x34),(0xc100,0xf7,0x24))
            self.assertEqual((d['afterNmi'],d['pc'],d['sp'],d['steps'],d['ram3'],d['ram4']),
                             (0xc110,0xc002,0xfd,10,0x31,0x42))

    @unittest.skipUnless(shutil.which('cc'),'C compiler required')
    def test_c_nmi_irq_lifted_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_rom(fixture(),out);src=out/'c_source'
            body='''#include "nes_runtime.h"
int main(void) {
 NesMachine m;if(nes_reset(&m))return 1;
 nes_set_irq_line(&m,1);
 if(nes_lifted_step(&m)||m.cpu.pc!=0xc001)return 2;
 if(nes_lifted_step(&m)||m.cpu.pc!=0xc110||m.cpu.sp!=0xfa)return 3;
 if((m.ram[0x1fb]&0x30)!=0x20)return 4;
 nes_request_nmi(&m);
 if(nes_lifted_step(&m)||m.cpu.pc!=0xc100||m.cpu.sp!=0xf7)return 5;
 if((m.ram[0x1f8]&0x34)!=0x24)return 6;
 for(int i=0;i<3;i++)if(nes_lifted_step(&m))return 7;
 if(m.cpu.pc!=0xc110||m.ram[3]!=0x31)return 8;
 nes_set_irq_line(&m,0);
 for(int i=0;i<4;i++)if(nes_lifted_step(&m))return 9;
 return (m.cpu.pc==0xc002&&m.cpu.sp==0xfd&&m.ram[4]==0x42&&m.steps==10)?0:10;
}'''
            h=src/'check.c';h.write_text(body)
            exe=src/'check'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                            str(src/'recovered_data.c'),str(src/'recovered_instructions.c'),
                            str(src/'lifted_code.c'),str(src/'nes_runtime.c'),
                            str(h),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
