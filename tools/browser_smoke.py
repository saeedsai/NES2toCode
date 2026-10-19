"""Optional real Chromium smoke test. Requires Playwright and Chromium.

Run: NES2TOCODE_CHROMIUM=/usr/bin/chromium python -m tools.browser_smoke
"""
import os
import tempfile
from pathlib import Path
from nesrev.browser import export_browser
from nesrev.rom import parse_rom

def main():
    from playwright.sync_api import sync_playwright
    code=bytes([0xa9,1,0x8d,0x16,0x40,0xa9,0,0x8d,0x16,0x40,
                0xad,0x16,0x40,0x85,0x02,0x4c,0x0f,0xc0])
    prg=bytearray([0xea]*16384);prg[:len(code)]=code;prg[-6:]=bytes([0,0xc0])*3
    h=bytearray(16);h[:4]=bytes([78,69,83,26]);h[4]=1
    with tempfile.TemporaryDirectory() as d:
        out=Path(d);export_browser(parse_rom(bytes(h)+prg),out)
        html=(out/'index.html').read_text(encoding='utf-8')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=os.environ.get('NES2TOCODE_CHROMIUM'))
            for mobile in (False,True):
                page=browser.new_page(viewport={'width':375 if mobile else 1280,'height':812},
                                      is_mobile=mobile,has_touch=mobile)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.set_content(html)
                assert page.locator('button[data-pad]').count()==8
                if mobile:
                    page.locator('button[data-pad="A"]').dispatch_event('pointerdown',{'pointerId':1,'pointerType':'touch'})
                else:
                    page.keyboard.down('z')
                for _ in range(6):page.locator('#step').click()
                assert '"ram2": 1' in page.locator('#status').inner_text()
                assert not errors,errors
                page.close()
            browser.close()
    print('PASS: real Chromium desktop keyboard and mobile touch, RAM[2]=1')

if __name__=='__main__':
    main()
