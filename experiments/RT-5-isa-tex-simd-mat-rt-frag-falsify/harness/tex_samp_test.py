#!/usr/bin/env python3
# tex_samp_test.py -- falsify sampler-slot = op+5. tex_sample.metal samples t0 via
# s0 and t1 via s1. Make t0 a 2x1 [red|blue] texture; sample at (0.5,0.5):
#   nearest -> one texel (red-channel 0 or 1); linear -> average (red 0.5).
# s0=nearest, s1=linear. Splice sample#0's op+5 (0x00->0x01) => should switch
# the filter used on t0 from nearest to linear.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SRC="kernels/tex_sample.metal"
def locate(a):
    o=subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True); return int(o.split()[0])
def find_first(buf):
    for j in range(len(buf)-14):
        if (buf[j]&0x0f)==0x05 and (buf[j+1]&0xf0)==0x80 and buf[j+2]==0x0c: return j
def texrun(archive):
    cmd=["./texrun","--archive",archive,"--source",SRC,"--function","k","--no-fast-math","--grid","1","--tg","1",
         "--tex","0=2,1,255,0,0,255,0,0,255,255","--tex","1=1,1,0,255,255,255",
         "--samp","0=nearest","--samp","1=linear","--out","0=32"]
    out=subprocess.check_output(cmd,text=True)
    for ln in out.splitlines():
        if ln.startswith("OUT "):
            b=bytes.fromhex(ln.split()[2]); return [struct.unpack("<f",b[i:i+4])[0] for i in range(0,len(b),4)]
def main():
    arch="txs.bin"; subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",SRC])
    moff=locate(arch); base=bytearray(open(arch,"rb").read())
    comp=find_first(base[moff:moff+120]); sop=comp+4
    print(f"# sample#0 sampler-op@+0x{sop:02x}, op bytes {bytes(base[moff+sop:moff+sop+10]).hex()}")
    r=texrun(arch); print("baseline out[0] (t0 via s0=nearest):", [f'{x:.3f}' for x in r[:4]])
    for label,rel,vals in [("op+5 samp",sop+5,[0x00,0x01,0x02,0x03,0x80])]:
        for v in vals:
            buf=bytearray(base); buf[moff+rel]=v; open("txspl.bin","wb").write(buf)
            try: rr=texrun("txspl.bin"); s=[f'{x:.3f}' for x in rr[:4]]
            except subprocess.CalledProcessError: s="FAULT"
            print(f"  {label} +0x{rel-moff if rel>moff else rel:02x} = 0x{v:02x} -> out[0]={s}")
if __name__=="__main__": main()
