#!/usr/bin/env python3
# uscread2.py — robust USC arg-buffer parser. Scans for the 2-pointer header:
# two 8-byte LE self-referential GPU VAs (high32==0x00000100) pointing within the BO.
# Verifies num_tex=(samp-tex)/0x20, num_samp=(term-samp)/8.
import sys,re
def load(path):
    data=bytearray(); base=0
    for line in open(path):
        if line.startswith('#'):
            m=re.search(r'gpu_va=0x([0-9a-f]+)',line)
            if m: base=int(m.group(1),16)
            continue
        m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\0'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return base,bytes(data)
def u64(d,o): return int.from_bytes(d[o:o+8],'little')
def u32(d,o): return int.from_bytes(d[o:o+4],'little')
base,d=load(sys.argv[1])
exp_t=int(sys.argv[2]) if len(sys.argv)>2 else None
exp_s=int(sys.argv[3]) if len(sys.argv)>3 else None
lo,hi=base,base+0x8000
# find first offset where two consecutive 8B values are self-referential VAs
hdr=None
for o in range(0,min(len(d),0x1000)-16,8):
    a=u64(d,o); b=u64(d,o+8)
    if lo<=a<hi and lo<=b<hi and (a>>32)==0x00000100 and b>=a:
        hdr=o; tex_ptr=a; samp_ptr=b; break
print(f"argbuf base={base:#x} exp(tex={exp_t},samp={exp_s})")
if hdr is None:
    print("  NO self-referential 2-ptr header found in first 0x1000 bytes")
    # still report terminator
    for o in range(0,min(len(d),0x1000),4):
        if u32(d,o)==0x60000000: print(f"  terminator @ off {o:#x}"); break
    sys.exit(0)
term_off=None
for o in range(hdr+0x10,min(len(d),0x1000),4):
    if u32(d,o)==0x60000000: term_off=o; break
term_va=base+term_off if term_off is not None else None
print(f"  header @ off {hdr:#x}")
print(f"    tex_ptr ={tex_ptr:#x} (off {tex_ptr-base:#x})")
print(f"    samp_ptr={samp_ptr:#x} (off {samp_ptr-base:#x})")
if term_off is not None: print(f"    terminator 0x60000000 @ off {term_off:#x}")
nt=(samp_ptr-tex_ptr)//0x20
ok_t = (exp_t is None) or (nt==exp_t)
print(f"    num_tex=(samp-tex)/0x20 = {nt}  {'OK' if ok_t else 'MISMATCH exp '+str(exp_t)}")
if term_va is not None:
    ns=(term_va-samp_ptr)//8
    ok_s=(exp_s is None) or (ns==exp_s)
    print(f"    num_samp=(term-samp)/8 = {ns}  {'OK' if ok_s else 'MISMATCH exp '+str(exp_s)}")
