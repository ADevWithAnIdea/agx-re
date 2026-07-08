#!/usr/bin/env python3
# uscread.py — parse the USC argument buffer (0x10000248000): 2-ptr header
# [tex-array VA][sampler-array VA], then 32B tex descriptors, then 8B sampler
# descriptors, then a 0x60000000 terminator.  Verify:
#   num_textures = (samp_ptr - tex_ptr)/0x20 ; num_samplers = (term - samp_ptr)/8
# Usage: uscread.py <argbuf.hex> [expected_tex] [expected_samp]
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
tex_ptr=u64(d,0); samp_ptr=u64(d,8)
# find terminator 0x60000000 scanning 32-bit words
term_off=None
for o in range(0x10,min(len(d),0x800),4):
    if u32(d,o)==0x60000000: term_off=o; break
term_va = base + term_off if term_off is not None else None
print(f"argbuf base={base:#x}")
print(f"  hdr[0] tex_ptr ={tex_ptr:#x}  (off {tex_ptr-base:#x})" if tex_ptr>=base else f"  hdr[0]={tex_ptr:#x}")
print(f"  hdr[1] samp_ptr={samp_ptr:#x}  (off {samp_ptr-base:#x})" if samp_ptr>=base else f"  hdr[1]={samp_ptr:#x}")
if term_off is not None: print(f"  terminator 0x60000000 @ off {term_off:#x} (va {term_va:#x})")
if tex_ptr and samp_ptr and samp_ptr>=tex_ptr:
    nt=(samp_ptr-tex_ptr)//0x20
    print(f"  num_textures = (samp-tex)/0x20 = {nt}", f"[expected {exp_t}]" if exp_t is not None else "")
if samp_ptr and term_va and term_va>=samp_ptr:
    ns=(term_va-samp_ptr)//8
    print(f"  num_samplers = (term-samp)/8   = {ns}", f"[expected {exp_s}]" if exp_s is not None else "")
