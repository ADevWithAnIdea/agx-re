#!/usr/bin/env python3
# Map every byte of a target instruction: for each byte offset within the
# instruction, sweep 0..255 and summarise how out0 responds. Classifies whether
# the byte moves the INDEX (out0 becomes a[k]=100k+3) vs some other effect.
import sys, os, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

SRC="kernels/bank.metal"; ARCH="bank.bin"
MAIN_OFF=int(subprocess.check_output(["python3","agxparse.py",ARCH,"--locate","_agc.main"],text=True).split()[0])
INSN_OFF=int(sys.argv[1],0)   # offset of target instruction within _agc.main
INSN_LEN=int(sys.argv[2],0)   # length in bytes
base=open(ARCH,"rb").read()
ins={2:"a_map.bin",3:"in_idx.bin"}
open("in_idx.bin","wb").write(struct.pack("<4I",5,6,7,9))
outs={0:4,1:4}

def a_index(v):  # invert a[k]=100k+3 -> k if exact
    if (v-3)%100==0 and v>=3: return (v-3)//100
    return None

r=PersistRunner(source=SRC,function="k",fast_math=False,agxrun_persist="./agxrun_persist")
try:
    for bo in range(INSN_LEN):
        abspos=MAIN_OFF+INSN_OFF+bo
        orig=base[abspos]
        idx_hits={}   # out0-as-a[k] -> list of byte values
        raw_hits={}   # small raw values (dest confound) -> list
        other=set(); nstatus={}
        for v in range(256):
            sp=bytearray(base); sp[abspos]=v
            open("sp.bin","wb").write(sp)
            resp=r.request(archive="sp.bin",grid=1,tg=1,ins=ins,outs=outs,timeout=5)
            st=resp["status"]; nstatus[st]=nstatus.get(st,0)+1
            if st!="OK":
                continue
            o0=struct.unpack("<I",resp["outs"][0])[0]
            k=a_index(o0)
            if k is not None and k!=5:
                idx_hits.setdefault(k,[]).append(v)
            elif o0 in (6,7,9,0) and o0!=5:
                raw_hits.setdefault(o0,[]).append(v)
            elif k!=5 and o0!=503:
                other.add(o0)
        idxs=sorted(idx_hits.keys())
        raws=sorted(raw_hits.keys())
        print(f"byte+{bo:<2d} (abs {abspos}, orig 0x{orig:02x}) status={nstatus} "
              f"INDEX->a[k] k in {idxs}  RAW(dest?) {raws}  other#{len(other)}")
        # show the low end of the index map if this byte moves the index
        if idxs:
            lo=sorted((v,k) for k,vs in idx_hits.items() for v in vs)[:8]
            print("        idx map (byteval->k):", ", ".join(f"0x{v:02x}->{k}" for v,k in lo))
finally:
    r.close()
