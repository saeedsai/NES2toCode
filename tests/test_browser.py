"""Standalone JavaScript/HTML diagnostic regression tests; not game-play parity."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from nesrev.browser import export_browser
from nesrev.rom import parse_rom


def rom(code, mapper=0, chr_data=None):
    count = 3 if mapper == 2 else 1
    prg = bytearray([0xea] * (count * 16384))
    if mapper == 2:
        prg[32768:32768 + len(code)] = code
    else:
        prg[:len(code)] = code
    start = 0xc000
    prg[-6:] = bytes([start & 255, start >> 8]) * 3
    if chr_data is None:
        chr_data = bytes(range(256)) * 32
    header = bytearray(16)
    header[:4] = b'NES\x1a'
    header[4] = len(prg) // 16384
    header[5] = len(chr_data) // 8192
    header[6] = (mapper & 15) << 4
    header[7] = mapper & 0xf0
    return parse_rom(bytes(header) + prg + chr_data)


@unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
class BrowserTests(unittest.TestCase):
    def node(self, output, statements):
        js = """const p=process.argv[1];require(p+'/rom_payload.js');
        const {Machine,OPCODES}=require(p+'/nes_runtime.js');
        const m=new Machine(globalThis.NES_PAYLOAD);""" + statements
        proc = subprocess.run(['node', '-e', js, str(output)], capture_output=True,
                              text=True, check=True)
        return json.loads(proc.stdout)

    def test_generated_html_is_self_contained_and_cpu_matches_known_output(self):
        code=bytes([0xa9,0x7f,0x18,0x69,0x01,0x10,0x03,0x85,0x02,0x4c,0x09,0xc0])
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'browser'
            export_browser(rom(code),out)
            html=(out/'index.html').read_text()
            self.assertEqual(html.count('<script>'),3)
            self.assertNotIn('src=',html)
            self.assertIn('NOT PLAYABLE',html)
            a=self.node(out, "m.run(6);console.log(JSON.stringify({s:m.snapshot(),len:m.chr.length,official:OPCODES.filter(Boolean).length,first:m.prg[0]}));")
            self.assertEqual(a['s']['ram2'],0x80)
            self.assertEqual(a['s']['a'],0x80)
            self.assertEqual(a['s']['pc'],0xc009)
            self.assertEqual(a['len'],8192)
            self.assertEqual(a['first'],0xa9)
            self.assertEqual(a['official'],151)
            self.assertEqual(a['s']['steps'],6)

    def test_mapper2_bank_switch(self):
        code=bytes([0xa9,0x01,0x8d,0x00,0x80,0x4c,0x00,0x80])
        cart=rom(code,mapper=2)
        prg=bytearray(cart.prg)
        prg[16384:16384+7]=bytes([0xa9,0x55,0x85,0x02,0x4c,0x04,0x80])
        raw=cart.header+bytes(prg)+cart.chr
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'browser'
            export_browser(parse_rom(raw),out)
            s=self.node(out,"m.run(5);console.log(JSON.stringify(m.snapshot()));")
            self.assertEqual(s['ram2'],0x55)
            self.assertEqual(s['steps'],5)
            self.assertEqual(s['pc'],0x8004)

    def test_mapper2_can_select_final_bank_in_lower_window(self):
        cart=rom(bytes([0xa9,0x42]),mapper=2)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'browser'
            export_browser(cart,out)
            data=self.node(out, "m.write(0x8000,2);console.log(JSON.stringify({lower:m.read(0x8000),upper:m.read(0xc000)}));")
            self.assertEqual(data,{'lower':0xa9,'upper':0xa9})

    @unittest.skipUnless(shutil.which('cc'), 'C compiler not installed')
    def test_mapper2_c_runtime_can_select_final_bank(self):
        from nesrev.exporter import export_rom
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'c_source'
            export_rom(rom(bytes([0xa9,0x42]),mapper=2),Path(d))
            harness=source/'check_bank.c'
            harness.write_text('#include "nes_runtime.h"\n'
                               'int main(void) { NesMachine m; if(nes_reset(&m))return 1; '
                               'nes_write(&m,0x8000,2); '
                               'return nes_read(&m,0x8000)==0xa9 ? 0 : 2; }\n')
            exe=source/'check_bank'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                            str(source/'recovered_data.c'),str(source/'nes_runtime.c'),
                            str(harness),'-o',str(exe)],check=True,capture_output=True,text=True)
            subprocess.run([str(exe)],check=True,capture_output=True,text=True)

    def test_unsupported_mapper_and_chr_ram(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'browser'
            export_browser(rom(bytes([0xea]),mapper=4,chr_data=b''),out)
            s=self.node(out,"console.log(JSON.stringify({s:m.snapshot(),tiles:m.chr.length}));")
            self.assertEqual(s['tiles'],0)
            self.assertTrue(s['s']['halted'])
            self.assertIn('unsupported',s['s']['error'])

    def test_dom_button_integration_with_canvas_stub(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'browser'
            export_browser(rom(bytes([0xa9,0x42,0x85,0x02,0x4c,0x04,0xc0])),out)
            js=r'''
            const fs=require('fs'),vm=require('vm');
            const html=fs.readFileSync(process.argv[1]+'/index.html','utf8');
            const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
            const nodes={};let drawCount=0;
            const ctx={createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),putImageData:()=>drawCount++};
            globalThis.document={getElementById:(id)=>nodes[id]??(nodes[id]={textContent:'',hidden:false,disabled:false,getContext:()=>ctx})};
            for(const script of scripts)vm.runInThisContext(script);
            nodes.step.onclick();nodes.step.onclick();
            console.log(JSON.stringify({text:nodes.status.textContent,drawCount,info:nodes.info.textContent}));
            '''
            proc=subprocess.run(['node','-e',js,str(out)],capture_output=True,text=True,check=True)
            data=json.loads(proc.stdout)
            self.assertIn('"a": 66',data['text'])
            self.assertIn('"ram2": 66',data['text'])
            self.assertEqual(data['drawCount'],1)
            self.assertIn('Mapper 0',data['info'])


if __name__=='__main__':
    unittest.main()
