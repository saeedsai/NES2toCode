"""Source-preserving JS 6502 research workbench exporter, not a playable game conversion."""
import base64
import json
from pathlib import Path
from .opcodes import OPCODES


def export_browser(cart, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    templ = Path(__file__).parent/'templates'
    table = [list(OPCODES[i][:2]) if i in OPCODES else None for i in range(256)]
    runtime = (templ/'nes_runtime.js').read_text(encoding='utf-8').replace(
        '__OPCODE_TABLE__', json.dumps(table, separators=(',', ':')))
    payload = {
        'format': 'NES 2.0' if cart.nes2 else 'iNES 1.0',
        'mapper': cart.mapper,
        'sha256': cart.sha256,
        'prg': base64.b64encode(cart.prg).decode('ascii'),
        'chr': base64.b64encode(cart.chr).decode('ascii'),
        'trainer': base64.b64encode(cart.trainer).decode('ascii')
    }
    # Embedded scripts need only machine-produced base64, digits, and fixed metadata.
    image = 'globalThis.NES_PAYLOAD=' + json.dumps(payload, separators=(',', ':')) + ';'
    ui = (templ/'browser_ui.js').read_text(encoding='utf-8')
    (out/'nes_runtime.js').write_text(runtime, encoding='utf-8')
    (out/'rom_payload.js').write_text(image+'\n', encoding='utf-8')
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NES2toCode — CPU/CHR Analysis Workbench</title>
<style>body{font:16px system-ui;background:#101c2a;color:#e6eef3;max-width:1000px;margin:auto;padding:22px}
button{padding:10px 14px;margin:4px;background:#294563;color:white;border:1px solid #688ba8;border-radius:6px;cursor:pointer}
button:disabled{opacity:.4}pre{background:#18283b;padding:16px;overflow:auto;white-space:pre-wrap}
canvas{width:min(100%,512px);height:auto;image-rendering:pixelated;border:1px solid #60798c}
.notice{border-left:3px solid #ffce70;padding:10px 14px;background:#2b2b35}</style></head><body>
<h1>NES2toCode — CPU/CHR Analysis Workbench</h1>
<p class="notice"><b>NOT PLAYABLE.</b> This runs official 6502 instruction semantics for select mappers with
placeholder CPU I/O. It does NOT emulate the NES PPU, APU, rendering, audio, input, IRQ timing,
or unofficial opcodes. Extracted graphics are raw 2-bit tile indices, not game sprites.</p>
<p id="info"></p><section><h2>CPU diagnostic</h2>
<button id="step">Step instruction</button><button id="run">Run 1000 steps</button>
<button id="reset">Reset CPU</button><pre id="status"></pre></section>
<section><h2>CHR tiles</h2><p id="nochr" hidden>No CHR-ROM. CHR-RAM may be generated dynamically by the game.</p>
<button id="prev">Previous</button><button id="next">Next</button><p id="page"></p>
<canvas id="tiles" width="128" height="128"></canvas></section>
<script>'''+image+'''</script>
<script>'''+runtime+'''</script>
<script>'''+ui+'''</script></body></html>'''
    (out/'index.html').write_text(html, encoding='utf-8')
    (out/'README.md').write_text(
        '# JavaScript/HTML analysis workbench\n\nOpen `index.html` in a browser; everything is embedded.\n'
        '`nes_runtime.js` is separately testable under Node.js; `rom_payload.js` includes original PRG/CHR bytes.\n'
        'The 151 official 6502 opcodes are dispatched in a non-cycle-accurate research runtime for '
        'mappers 0, 2 and 3 only. Unsupported mappers are rejected for CPU execution. '
        'PPU/APU/controller/timing/IRQ/unofficial opcodes are NOT implemented. '
        'ROM PRG/CHR is original embedded data; **this is not reconstructed original JS source code or playable gameplay**.\n'
        'Treat generated files containing ROM data as copyright-sensitive.\n', encoding='utf-8')
    return True
