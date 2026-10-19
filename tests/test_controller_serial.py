"""Synthetic NES controller serial-input tests; not real-game parity."""
import json, shutil, subprocess, tempfile, unittest
from pathlib import Path
from nesrev.rom import parse_rom
from nesrev.browser import export_browser
from nesrev.exporter import export_rom

def fixture(mapper=0):
    n=3 if mapper==2 else 1
    prg=bytearray([0xea]*(n*16384))
    prg[-6:]=bytes([0,0xc0])*3
    if mapper==2: prg[32768]=0xa9
    h=bytearray(16);h[:4]=bytes([78,69,83,26]);h[4]=n;h[6]=mapper<<4
    return parse_rom(bytes(h)+prg)

class ControllerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_js_two_ports_and_strobe(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_browser(fixture(),out)
            js="""require(process.argv[1]+'/rom_payload.js');
            const m=new (require(process.argv[1]+'/nes_runtime.js').Machine)(globalThis.NES_PAYLOAD);
            m.setController(0,0x55);m.setController(1,0xaa);m.write(0x4016,1);
            const high=[m.read(0x4016),m.read(0x4016)];m.write(0x4016,0);
            const a=Array.from({length:10},()=>m.read(0x4016));
            const b=Array.from({length:10},()=>m.read(0x4017));
            console.log(JSON.stringify({high,a,b}));"""
            r=subprocess.run(['node','-e',js,str(out)],capture_output=True,text=True,check=True)
            d=json.loads(r.stdout)
            self.assertEqual(d['high'],[1,1])
            self.assertEqual(d['a'],[1,0,1,0,1,0,1,0,1,1])
            self.assertEqual(d['b'],[0,1,0,1,0,1,0,1,1,1])

    @unittest.skipUnless(shutil.which('cc'),'C compiler required')
    def test_c_controller_and_final_bank(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_rom(fixture(mapper=2),out);src=out/'c_source'
            body='''#include "nes_runtime.h"
int main(void) {
 NesMachine m;if(nes_reset(&m))return 1;
 nes_write(&m,0x8000,2);if(nes_read(&m,0x8000)!=0xa9)return 2;
 nes_set_controller(&m,0,0x55);nes_set_controller(&m,1,0xaa);
 nes_write(&m,0x4016,1);if(nes_read(&m,0x4016)!=1)return 3;
 nes_write(&m,0x4016,0);
 const char *bits[2]={"1010101011","0101010111"};
 for(int p=0;p<2;p++)for(int i=0;i<10;i++)
  if(nes_read(&m,(uint16_t)(0x4016+p))!=bits[p][i]-'0')return 4;
 return 0;
}'''
            h=src/'check.c';h.write_text(body)
            exe=src/'check'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(src/'recovered_data.c'),
                            str(src/'nes_runtime.c'),str(h),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
