#!/usr/bin/env python3
# Falsify op+2 (variant) and op+6 (mode/filtered) and comp+3 (gather component).
# Uses tex_sample.metal: t0 = 2x2 [R,G / B,W]; sample#0 = t0.sample(s0,(0.5,0.5)).
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SRC="kernels/tex_sample.metal"
def locate(a): return int(subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True).split()[0])
def find_first(buf):
    for j in range(len(buf)-14):
        if (buf[j]&0x0f)==0x05 and (buf[j+1]&0xf0)==0x80 and buf[j+2]==0x0c: return j
def texrun(archive):
    cmd=["./texrun","--archive",archive,"--source",SRC,"--function","k","--no-fast-math","--grid","1","--tg","1",
         # 2x2: (0,0)=red (1,0)=green (0,1)=blue (1,1)=white
         "--tex","0=2,2,255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255","--tex","1=1,1,50,100,150,255",
         "--samp","0=linear","--samp","1=nearest","--out","0=32"]
    out=subprocess.check_output(cmd,text=True)
    for ln in out.splitlines():
        if ln.startswith("OUT "):
            b=bytes.fromhex(ln.split()[2]); return [struct.unpack("<f",b[i:i+4])[0] for i in range(0,len(b),4)]
def main():
    arch="txv.bin"; subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",SRC])
    moff=locate(arch); base=bytearray(open(arch,"rb").read())
    comp=find_first(base[moff:moff+120]); sop=comp+4
    print(f"# comp@+0x{comp:02x} sop@+0x{sop:02x} baseline op {bytes(base[moff+sop:moff+sop+10]).hex()} comp+3=0x{base[moff+comp+3]:02x}")
    r=texrun(arch); print("baseline (linear sample):", [f'{x:.3f}' for x in r[:4]])
    def sweep(label, rel, vals):
        for v in vals:
            buf=bytearray(base); buf[moff+rel]=v; open("txvs.bin","wb").write(buf)
            try: rr=texrun("txvs.bin"); s=[f'{x:.3f}' for x in rr[:4]]
            except subprocess.CalledProcessError: s="FAULT"
            print(f"  {label} 0x{v:02x} -> {s}")
    print("-- op+2 variant --"); sweep("op+2", sop+2, [0x09,0x00,0x17,0x04,0x07,0x13,0x39,0x20,0x29])
    print("-- op+6 mode (0x10 filtered / 0x00) --"); sweep("op+6", sop+6, [0x10,0x00,0x20])
    print("-- comp+3 result-desc (gather comp) --"); sweep("comp+3", comp+3, [0x18,0xa4,0xac,0xb4,0xbc,0xb8,0xa0])
if __name__=="__main__": main()
