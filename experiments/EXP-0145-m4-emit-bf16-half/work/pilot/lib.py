import os,struct,importlib.util,json
REPO='/Users/user/asahi_re/public/agx-re'
EXP=os.path.join(REPO,'experiments','EXP-0145-m4-emit-bf16-half')
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=lm('agxparse',os.path.join(REPO,'tools','shdump','agxparse.py'))
PersistRunner=lm('persistrun',os.path.join(REPO,'tools','agxtest','persistrun.py')).PersistRunner
import sys; sys.path.insert(0,os.path.join(REPO,'tools','agx-isa')); import isadb

def compile_carrier(src,out,fn='k'):
    import subprocess
    r=subprocess.run([os.path.join(EXP,'work','bin','shdump'),'-o',out,'-f',fn,'--no-fast-math',src],
                     capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError(r.stderr+r.stdout)
    return out

def load_base(binpath):
    buf=open(binpath,'rb').read()
    off,ln=agxparse.locate_region(buf,'_agc.main')
    _,pieces=agxparse.extract_agx(buf)
    return buf,off,pieces['_agc.main']

def disasm(b,label=''):
    recs,left=isadb.disassemble(b); off=0; out=[]
    for r in recs:
        out.append((off,r['mnemonic'],b[off:off+r['length']].hex(),r['fields']))
        off+=r['length']
    return out,left

def show(b):
    recs,left=disasm(b)
    for off,m,h,f in recs:
        print("  +0x%03x %-18s %-30s %s"%(off,m,h,json.dumps(f)))
    if left: print("  leftover",left.hex())

def wf(path,vals):
    open(path,'wb').write(b''.join(struct.pack('<f',v) for v in vals)); return path

def f32(h):
    return struct.unpack('<f',bytes.fromhex(h))[0] if len(h)==8 else None

def bf16_bits_rne(x):
    u=struct.unpack('<I',struct.pack('<f',float(x)))[0]
    if (u&0x7F800000)==0x7F800000 and (u&0x7FFFFF): return (u>>16)|0x0040
    lsb=(u>>16)&1
    return ((u+0x7FFF+lsb)>>16)&0xFFFF
def bf16_bits_rtz(x):
    return (struct.unpack('<I',struct.pack('<f',float(x)))[0]>>16)&0xFFFF
def bf2f(bits):
    return struct.unpack('<f',struct.pack('<I',(bits&0xFFFF)<<16))[0]
def h2f(bits):
    import numpy
def fp16_to_f32(bits):
    s=(bits>>15)&1; e=(bits>>10)&0x1F; m=bits&0x3FF
    if e==0: v=(m/1024.0)*(2.0**-14)
    elif e==31: v=float('inf') if m==0 else float('nan')
    else: v=(1.0+m/1024.0)*(2.0**(e-15))
    return -v if s else v
