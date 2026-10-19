"""Browser controller wiring and final-bank CFG tests (synthetic ROMs)."""
import json, shutil, subprocess, tempfile, unittest
from pathlib import Path
from nesrev.rom import parse_rom
from nesrev.browser import export_browser
from nesrev.disasm import Analyzer

class BrowserInputAndCFG(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_keyboard_updates_controller_serial_port(self):
        code=bytes([0xa9,1,0x8d,0x16,0x40,0xa9,0,0x8d,0x16,0x40,
                    0xad,0x16,0x40,0x85,0x02,0x4c,0x0f,0xc0])
        prg=bytearray([0xea]*16384);prg[:len(code)]=code;prg[-6:]=bytes([0,0xc0])*3
        h=bytearray(16);h[:4]=bytes([78,69,83,26]);h[4]=1
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_browser(parse_rom(bytes(h)+prg),out)
            js=r"""const fs=require('fs'),vm=require('vm');
            const html=fs.readFileSync(process.argv[1]+'/index.html','utf8');
            const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
            const nodes={},events={};
            const ctx={createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),putImageData:()=>{}};
            globalThis.document={getElementById:(id)=>nodes[id]??(nodes[id]={textContent:'',hidden:false,disabled:false,getContext:()=>ctx})};
            globalThis.window={addEventListener:(type,fn)=>events[type]=fn};
            for(const s of scripts)vm.runInThisContext(s);
            events.keydown({code:'KeyZ',preventDefault:()=>{}});
            for(let i=0;i<6;i++)nodes.step.onclick();
            console.log(JSON.stringify({status:nodes.status.textContent,buttons:html.match(/data-pad=/g).length}));"""
            r=subprocess.run(['node','-e',js,str(out)],capture_output=True,text=True,check=True)
            data=json.loads(r.stdout)
            self.assertIn('"ram2": 1',data['status'])
            self.assertEqual(data['buttons'],8)

    def test_final_uxrom_bank_in_switchable_cfg(self):
        prg=bytearray([2]*(3*16384))
        prg[32768:32771]=bytes([0x4c,0x03,0x80])
        prg[32771:32774]=bytes([0xa9,0x77,0x60])
        prg[-6:]=bytes([0,0xc0])*3
        h=bytearray(16);h[:4]=bytes([78,69,83,26]);h[4]=3;h[6]=0x20
        found={(x.bank,x.offset,x.mnemonic) for x in Analyzer(parse_rom(bytes(h)+prg)).analyze().instruction_list()}
        self.assertIn((2,3,'LDA'),found)
        self.assertIn((2,5,'RTS'),found)
