/* NES2toCode generated JavaScript CPU workbench.
 * CPU semantics are experimental, not cycle-accurate; PPU/APU, DMA and frame timing are stubs; controller serial input and externally injected interrupts are diagnostic-only.
 * Do not describe this diagnostic as a playable ROM-to-HTML conversion. */
(function (root) {
  'use strict';
  const OPCODES = __OPCODE_TABLE__;
  const F = Object.freeze({C:1,Z:2,I:4,D:8,B:16,U:32,V:64,N:128});
  function bytes(b64) {
    const str = atob(b64), out = new Uint8Array(str.length);
    for (let i=0;i<str.length;i++) out[i]=str.charCodeAt(i);
    return out;
  }
  class Machine {
    constructor(payload) {
      this.mapper=payload.mapper;
      this.prg=bytes(payload.prg);
      this.chr=bytes(payload.chr);
      this.trainer=bytes(payload.trainer);
      // Controller bit order: A, B, Select, Start, Up, Down, Left, Right.
      this.controllers=new Uint8Array(2);
      this.controllerShift=new Uint8Array(2);
      this.controllerReads=new Uint8Array(2);
      this.controllerStrobe=0;
      this.supported=[0,2,3].includes(this.mapper) &&
        (((this.mapper===0||this.mapper===3)&&[16384,32768].includes(this.prg.length)) ||
        (this.mapper===2 && this.prg.length>=32768 && this.prg.length%16384===0));
      this.reset();
    }
    romOffset(a) {
      a &= 65535;
      if (a<0x8000 || !this.supported) return -1;
      if (this.mapper===2) {
        const banks=this.prg.length/16384;
        const bank=a>=0xc000?banks-1:this.selectedPrg%banks;
        return bank*16384+(a&0x3fff);
      }
      return this.prg.length===16384?((a-0x8000)&0x3fff):a-0x8000;
    }
    setController(port, buttons) {
      if (!Number.isInteger(port) || port<0 || port>1) throw RangeError('Controller port must be 0 or 1');
      this.controllers[port]=buttons&255;
      if(this.controllerStrobe) this.latchControllers();
    }
    latchControllers() {
      this.controllerShift.set(this.controllers);
      this.controllerReads.fill(0);
    }
    readController(port) {
      if(this.controllerStrobe) return this.controllers[port]&1;
      if(this.controllerReads[port]>=8) return 1;
      const bit=this.controllerShift[port]&1;
      this.controllerShift[port]>>=1;
      this.controllerReads[port]++;
      return bit;
    }
    read(a) {
      a &= 65535;
      if (a<0x2000) return this.ram[a&0x7ff];
      if (a<0x4000) { this.ppuAccesses++; return 0; }
      if (a===0x4016 || a===0x4017) { this.apuAccesses++; return this.readController(a-0x4016); }
      if (a<0x4020) { this.apuAccesses++; return this.io[a&31]; }
      if (a>=0x6000 && a<0x8000) return this.sram[a-0x6000];
      if (a>=0x8000) { const off=this.romOffset(a);return off>=0&&off<this.prg.length?this.prg[off]:255; }
      return 255;
    }
    write(a,v) {
      a &= 65535; v &= 255;
      if (a<0x2000) {this.ram[a&0x7ff]=v;return;}
      if (a<0x4000) {this.ppuAccesses++;return;}
      if (a===0x4016) {
        this.apuAccesses++;
        this.io[a&31]=v;
        const previous=this.controllerStrobe;
        this.controllerStrobe=v&1;
        if(this.controllerStrobe || previous) this.latchControllers();
        return;
      }
      if (a<0x4020) {this.apuAccesses++;this.io[a&31]=v;return;}
      if (a>=0x6000&&a<0x8000) {this.sram[a-0x6000]=v;return;}
      if (a>=0x8000&&this.mapper===2) this.selectedPrg=v;
      if (a>=0x8000&&this.mapper===3) this.selectedChr=v;
    }
    reset() {
      this.ram=new Uint8Array(2048);
      this.sram=new Uint8Array(8192);
      this.io=new Uint8Array(32);
      if (this.trainer.length===512) this.sram.set(this.trainer,0x1000);
      this.selectedPrg=0;this.selectedChr=0;this.ppuAccesses=0;this.apuAccesses=0;
      this.controllerStrobe=0;this.latchControllers();
      this.nmiPending=false;this.irqLine=false;
      this.a=0;this.x=0;this.y=0;this.sp=0xfd;this.p=F.I|F.U;this.steps=0;
      this.halted=!this.supported;
      this.error=this.supported?'':`Mapper ${this.mapper} unsupported by JavaScript CPU workbench`;
      this.pc=this.supported?(this.read(0xfffc)|(this.read(0xfffd)<<8)):0;
      return this;
    }
    // External interrupt injection is diagnostic-only until a timed PPU/APU exists.
    requestNMI() { this.nmiPending=true; }
    setIRQLine(asserted) { this.irqLine=!!asserted; }
    serviceInterrupt() {
      const nmi=this.nmiPending;
      if(!nmi && (!this.irqLine || (this.p&F.I))) return false;
      if(nmi) this.nmiPending=false;
      this.push(this.pc>>8);
      this.push(this.pc&255);
      this.push((this.p&~F.B)|F.U);
      this.p=(this.p|F.I|F.U)&~F.B;
      const vector=nmi?0xfffa:0xfffe;
      this.pc=this.read(vector)|(this.read(vector+1)<<8);
      this.steps++;
      return true;
    }
    fetch() {const v=this.read(this.pc);this.pc=(this.pc+1)&65535;return v;}
    word() {const lo=this.fetch();return lo|(this.fetch()<<8);}
    zpWord(zp) {return this.read(zp&255)|(this.read((zp+1)&255)<<8);}
    address(mode) {
      switch (mode) {
        case 'imm': {const a=this.pc;this.pc=(this.pc+1)&65535;return a;}
        case 'zp':return this.fetch();
        case 'zpx':return (this.fetch()+this.x)&255;
        case 'zpy':return (this.fetch()+this.y)&255;
        case 'abs':return this.word();
        case 'absx':return (this.word()+this.x)&65535;
        case 'absy':return (this.word()+this.y)&65535;
        case 'indx':return this.zpWord((this.fetch()+this.x)&255);
        case 'indy':return (this.zpWord(this.fetch())+this.y)&65535;
        case 'ind': {const a=this.word();return this.read(a)|(this.read((a&0xff00)|((a+1)&255))<<8);}
        case 'rel': {const offset=this.fetch();return (this.pc+(offset<128?offset:offset-256))&65535;}
        default:return 0;
      }
    }
    flag(f,v) {this.p=v?(this.p|f):(this.p&~f);}
    nz(v) {this.flag(F.Z,(v&255)===0);this.flag(F.N,v&128);}
    push(v) {this.write(0x100|this.sp,v);this.sp=(this.sp-1)&255;}
    pop() {this.sp=(this.sp+1)&255;return this.read(0x100|this.sp);}
    cmp(a,v) {this.flag(F.C,a>=v);this.nz((a-v)&255);}
    adc(v) {
      const a=this.a, total=a+v+((this.p&F.C)?1:0), r=total&255;
      this.flag(F.C,total>255);
      this.flag(F.V,(~(a^v)&(a^r)&128)!==0);
      this.a=r;this.nz(r);
    }
    step() {
      if(this.halted)return false;
      if(this.serviceInterrupt())return true;
      const oldpc=this.pc, opcode=this.fetch(), entry=OPCODES[opcode];
      if(!entry){this.halted=true;this.error=`Unsupported opcode $${opcode.toString(16).padStart(2,'0')} at $${oldpc.toString(16).padStart(4,'0')}`;return false;}
      const [op,mode]=entry, ea=this.address(mode);
      let v=0;
      if(!['imp','acc','rel'].includes(mode)&&!['JMP','JSR','STA','STX','STY'].includes(op))v=this.read(ea);
      let r;
      switch(op) {
        case 'ADC':this.adc(v);break;
        case 'AND':this.a&=v;this.nz(this.a);break;
        case 'ASL':r=(mode==='acc'?this.a:v);this.flag(F.C,r&128);r=(r<<1)&255;this.nz(r);if(mode==='acc')this.a=r;else this.write(ea,r);break;
        case 'BCC':if(!(this.p&F.C))this.pc=ea;break;
        case 'BCS':if(this.p&F.C)this.pc=ea;break;
        case 'BEQ':if(this.p&F.Z)this.pc=ea;break;
        case 'BIT':this.flag(F.Z,(this.a&v)===0);this.flag(F.N,v&128);this.flag(F.V,v&64);break;
        case 'BMI':if(this.p&F.N)this.pc=ea;break;
        case 'BNE':if(!(this.p&F.Z))this.pc=ea;break;
        case 'BPL':if(!(this.p&F.N))this.pc=ea;break;
        case 'BRK':this.pc=(this.pc+1)&65535;this.push(this.pc>>8);this.push(this.pc);this.push(this.p|F.B|F.U);this.p|=F.I;this.pc=this.read(0xfffe)|(this.read(0xffff)<<8);break;
        case 'BVC':if(!(this.p&F.V))this.pc=ea;break;
        case 'BVS':if(this.p&F.V)this.pc=ea;break;
        case 'CLC':this.p&=~F.C;break;
        case 'CLD':this.p&=~F.D;break;
        case 'CLI':this.p&=~F.I;break;
        case 'CLV':this.p&=~F.V;break;
        case 'CMP':this.cmp(this.a,v);break;
        case 'CPX':this.cmp(this.x,v);break;
        case 'CPY':this.cmp(this.y,v);break;
        case 'DEC':r=(v-1)&255;this.write(ea,r);this.nz(r);break;
        case 'DEX':this.x=(this.x-1)&255;this.nz(this.x);break;
        case 'DEY':this.y=(this.y-1)&255;this.nz(this.y);break;
        case 'EOR':this.a^=v;this.nz(this.a);break;
        case 'INC':r=(v+1)&255;this.write(ea,r);this.nz(r);break;
        case 'INX':this.x=(this.x+1)&255;this.nz(this.x);break;
        case 'INY':this.y=(this.y+1)&255;this.nz(this.y);break;
        case 'JMP':this.pc=ea;break;
        case 'JSR':this.push((this.pc-1)>>8);this.push((this.pc-1)&255);this.pc=ea;break;
        case 'LDA':this.a=v;this.nz(v);break;
        case 'LDX':this.x=v;this.nz(v);break;
        case 'LDY':this.y=v;this.nz(v);break;
        case 'LSR':r=mode==='acc'?this.a:v;this.flag(F.C,r&1);r>>=1;this.nz(r);if(mode==='acc')this.a=r;else this.write(ea,r);break;
        case 'NOP':break;
        case 'ORA':this.a|=v;this.nz(this.a);break;
        case 'PHA':this.push(this.a);break;
        case 'PHP':this.push(this.p|F.B|F.U);break;
        case 'PLA':this.a=this.pop();this.nz(this.a);break;
        case 'PLP':this.p=(this.pop()&~F.B)|F.U;break;
        case 'ROL':r=mode==='acc'?this.a:v;{const c=(this.p&F.C)?1:0;this.flag(F.C,r&128);r=((r<<1)|c)&255;}this.nz(r);if(mode==='acc')this.a=r;else this.write(ea,r);break;
        case 'ROR':r=mode==='acc'?this.a:v;{const c=(this.p&F.C)?128:0;this.flag(F.C,r&1);r=(r>>1)|c;}this.nz(r);if(mode==='acc')this.a=r;else this.write(ea,r);break;
        case 'RTI':this.p=(this.pop()&~F.B)|F.U;this.pc=this.pop()|(this.pop()<<8);break;
        case 'RTS':this.pc=((this.pop()|(this.pop()<<8))+1)&65535;break;
        case 'SBC':this.adc(v^255);break;
        case 'SEC':this.p|=F.C;break;
        case 'SED':this.p|=F.D;break;
        case 'SEI':this.p|=F.I;break;
        case 'STA':this.write(ea,this.a);break;
        case 'STX':this.write(ea,this.x);break;
        case 'STY':this.write(ea,this.y);break;
        case 'TAX':this.x=this.a;this.nz(this.x);break;
        case 'TAY':this.y=this.a;this.nz(this.y);break;
        case 'TSX':this.x=this.sp;this.nz(this.x);break;
        case 'TXA':this.a=this.x;this.nz(this.a);break;
        case 'TXS':this.sp=this.x;break;
        case 'TYA':this.a=this.y;this.nz(this.a);break;
        default:throw Error('Unimplemented official instruction: '+op);
      }
      this.p|=F.U;
      this.steps++;
      return true;
    }
    run(n) {
      if(!Number.isInteger(n)||n<0||n>100000)throw RangeError('Run step count must be 0..100000');
      let done=0;while(done<n&&this.step())done++;
      return done;
    }
    snapshot() {return {pc:this.pc,a:this.a,x:this.x,y:this.y,sp:this.sp,p:this.p,steps:this.steps,ram2:this.ram[2],halted:this.halted,error:this.error,mapper:this.mapper,ppuAccesses:this.ppuAccesses,apuAccesses:this.apuAccesses};}
  }
  root.NESRuntime=Object.freeze({Machine,OPCODES});
  if(typeof module!=='undefined'&&module.exports)module.exports=root.NESRuntime;
})(globalThis);
