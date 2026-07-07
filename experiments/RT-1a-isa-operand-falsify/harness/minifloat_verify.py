#!/usr/bin/env python3
# Falsify the packed minifloat immediate: with a=0, out = 0 + K = K. Sweep the
# immediate byte (byte+1 of falu2i) full range for both signs, read the runtime
# float, and compare to the DB imm_decode formula. Print EVERY value + flag
# disagreements.
import sys, os, subprocess, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

ARCH="cadd.bin"; SRC="kernels/cadd.metal"
MAIN_OFF=int(subprocess.check_output(["python3","agxparse.py",ARCH,"--locate","_agc.main"],text=True).split()[0])
IMM_POS = MAIN_OFF + 0x12 + 1      # byte+1 of the falu2i at +0x12
SIGN_POS = MAIN_OFF + 0x12 + 2     # byte+2 holds imm_sign at bit3 (0x08)

def imm_decode(b1, sign):
    e=(b1>>4)&0xf; m=(b1>>1)&0x7
    v=(m/8.0)*(2.0**(9-11)) if e==8 else (1+m/8.0)*(2.0**(e-11))
    return -v if sign else v

base=open(ARCH,"rb").read()
open("zero.bin","wb").write(struct.pack("<f",0.0))
r=PersistRunner(source=SRC,function="k",fast_math=False,agxrun_persist="./agxrun_persist")
disc=[]; rows=[]
try:
    for sign in (0,1):
        for v in range(256):
            sp=bytearray(base)
            sp[IMM_POS]=v
            b2=sp[SIGN_POS]
            sp[SIGN_POS]=(b2|0x08) if sign else (b2 & ~0x08)
            open("mf.bin","wb").write(sp)
            resp=r.request(archive="mf.bin",grid=1,tg=1,ins={1:"zero.bin"},outs={0:4},timeout=5)
            st=resp["status"]
            got=struct.unpack("<f",resp["outs"][0])[0] if (st=="OK" and 0 in resp["outs"]) else None
            pred=imm_decode(v,sign)
            ok = (got is not None) and (abs(got-pred)<=1e-6*max(1,abs(pred)) or (got==0 and pred==0))
            rows.append((sign,v,pred,got,st,ok))
            if st=="OK" and not ok:
                disc.append((sign,v,pred,got))
finally:
    r.close()
# summary
print(f"# swept 512 (256 x 2 signs). discrepancies where STATUS OK but got!=pred: {len(disc)}")
for sign,v,pred,got in disc:
    print(f"  DISC sign={sign} b1=0x{v:02x} pred={pred!r} got={got!r}")
# also print the canonical documented examples
docex={0xb1:1.0,0xc1:2.0,0xb9:1.5,0xcd:3.5,0x85:0.0625,0xff:30.0}
print("# documented example checks (sign=0):")
for b1,exp in docex.items():
    row=[x for x in rows if x[0]==0 and x[1]==b1][0]
    print(f"  b1=0x{b1:02x} doc={exp} pred={row[2]} got={row[3]} status={row[4]}")
# report min/max representable and count of distinct OK values
oks=[(v,got) for sign,v,pred,got,st,o in rows if sign==0 and st=='OK' and got is not None]
print(f"# sign=0 OK count={len(oks)} min={min(g for _,g in oks)} max={max(g for _,g in oks)}")
