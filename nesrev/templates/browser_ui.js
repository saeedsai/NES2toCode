/* Inspect only: no NES PPU/APU emulation or full game renderer. */
(function () {
  'use strict';
  const payload = globalThis.NES_PAYLOAD;
  const m = new NESRuntime.Machine(payload);
  const info=document.getElementById('info'), status=document.getElementById('status');
  const canvas=document.getElementById('tiles'), ctx=canvas.getContext('2d');
  const totalTiles=Math.floor(m.chr.length/16);
  let page=0;
  info.textContent=`${payload.format} | Mapper ${payload.mapper} | PRG ${m.prg.length} bytes | CHR ${m.chr.length} bytes | ${totalTiles} tiles | SHA-256 ${payload.sha256}`;
  function render() {
    const s=m.snapshot();
    status.textContent=JSON.stringify(s,null,2)+'\n'+Array.from(m.ram.slice(0,32)).map(x=>x.toString(16).padStart(2,'0')).join(' ');
    document.getElementById('run').disabled=m.halted;
    document.getElementById('step').disabled=m.halted;
  }
  function draw() {
    const data=ctx.createImageData(128,128);
    const colors=[240,170,90,18];
    for(let t=0;t<256;t++) {
      const tileOffset=(page*256+t)*16;
      if(tileOffset+16>m.chr.length)continue;
      for(let y=0;y<8;y++)for(let x=0;x<8;x++){
        const mask=128>>x, lo=m.chr[tileOffset+y], hi=m.chr[tileOffset+8+y];
        const index=((lo&mask)?1:0)|((hi&mask)?2:0);
        const xx=(t%16)*8+x, yy=Math.floor(t/16)*8+y, i=(yy*128+xx)*4;
        data.data[i]=data.data[i+1]=data.data[i+2]=colors[index];data.data[i+3]=255;
      }
    }
    ctx.putImageData(data,0,0);
    document.getElementById('page').textContent=`CHR tiles ${page*256}–${Math.min((page+1)*256,totalTiles)-1} (raw color indices; not original palette)`;
    document.getElementById('prev').disabled=page===0;
    document.getElementById('next').disabled=(page+1)*256>=totalTiles;
  }
  // Browser input updates the controller's live state; $4016 strobe controls latching.
  const buttonBits={A:1,B:2,Select:4,Start:8,Up:16,Down:32,Left:64,Right:128};
  const keyMap={ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',
    KeyZ:'A',KeyX:'B',Enter:'Start',ShiftLeft:'Select',ShiftRight:'Select'};
  const keys=new Set(), pointers=new Set();
  function updatePad() {
    let mask=0;
    for(const b of keys) mask|=buttonBits[b];
    for(const b of pointers) mask|=buttonBits[b];
    m.setController(0,mask);
  }
  if(typeof window!=='undefined' && window.addEventListener) {
    window.addEventListener('keydown',e=>{const b=keyMap[e.code];if(!b)return;
      keys.add(b);updatePad();e.preventDefault();});
    window.addEventListener('keyup',e=>{const b=keyMap[e.code];if(!b)return;
      keys.delete(b);updatePad();e.preventDefault();});
    window.addEventListener('blur',()=>{keys.clear();pointers.clear();updatePad();});
  }
  if(typeof document.querySelectorAll==='function') {
    for(const b of document.querySelectorAll('button[data-pad]')) {
      const name=b.dataset.pad;
      b.addEventListener('pointerdown',e=>{pointers.add(name);b.classList.add('pressed');
        if(b.setPointerCapture)b.setPointerCapture(e.pointerId);updatePad();e.preventDefault();});
      const release=()=>{pointers.delete(name);b.classList.remove('pressed');updatePad();};
      b.addEventListener('pointerup',release);
      b.addEventListener('pointercancel',release);
      b.addEventListener('lostpointercapture',release);
    }
  }
  document.getElementById('step').onclick=()=>{m.step();render();};
  document.getElementById('run').onclick=()=>{m.run(1000);render();};
  document.getElementById('reset').onclick=()=>{m.reset();updatePad();render();};
  document.getElementById('prev').onclick=()=>{page--;draw();};
  document.getElementById('next').onclick=()=>{page++;draw();};
  document.getElementById('tiles').hidden=totalTiles===0;
  document.getElementById('nochr').hidden=totalTiles!==0;
  render();if(totalTiles)draw();
})();
