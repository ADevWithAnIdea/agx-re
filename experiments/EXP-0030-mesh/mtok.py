#!/usr/bin/env python3
# mtok.py — EXP-0030 merged AGX tokenizer: compute length rule (tools/agx-isa /
# EXP-0022 walk) + fragment/vertex rule (EXP-0029 frag_tok) + mesh candidates.
# Goal: tokenize object/mesh/fragment _agc.main + helper regions cleanly to the
# 0e000000 stop with zero leftover, so we can census byte0 groups and decide
# "dedicated mesh opcode vs known memory/ALU ops". CLEAN-ROOM: our own bytes.
import sys, os

def B(b,o): return b[o] if 0 <= o < len(b) else -1

def ilen(b, o):
    b0=b[o]; b1=B(b,o+1); b2=B(b,o+2); b3=B(b,o+3); b6=B(b,o+6); lo=b0&0x0f
    # --- terminators / preamble ---
    if b0==0x0e: return 4                                   # stop
    if b2==0x10 and b3==0x06: return 4                      # get_sr (Xe/X4 ..1006)
    if lo==0x0c: return 4                                   # preamble/get_sr
    # --- memory family ---
    if b0==0xe7: return 12 if b1==0x06 else 14              # store (frag color 12 / device 14)
    if b0==0x67: return 14                                  # load / atomic
    if b0==0xd7: return 16                                  # texture/mesh-index write (memory store)
    if b0==0x87 and b2==0x54: return 6
    if b0==0x07 and b2==0x54: return 6                      # attribute/barrier
    if b0==0x97: return 10
    if b0==0xa7 and b2==0x54: return 10
    if b0==0xa7: return 8 if b1==0x07 else (10 if (b1&1) else 12)
    # --- interpolation / low-nibble-f ALU ---
    if b0 in (0x2f,0xaf,0x3f) and b2==0x54: return 8 if b6==0x0a else 10
    if b0 in (0x2f,0xaf): return 10                         # SFU
    if b0 in (0x1f,0x9f) and b2==0x54: return 6
    # --- integer ALU ---
    if b0 in (0x9f,0x1f): return 10 if (b1&1) else 12
    if b0==0x27: return 10 if b1==0x07 else (12 if b1 in (0,0x10) else 8)
    # --- float / misc ALU ---
    if lo==0x09:
        if b2==0x38: return 4
        return 8 if (b2&0x02) else 6
    if b0==0x0b: return 10
    if b0==0x11: return 8 if (b2&0x02) else 6
    if b0==0x02: return 6
    if b0==0x12: return 14 if (b2&0x0f)==0x0d else 6
    if b0==0x0a: return 6
    if b0==0x13: return 4
    if b0 in (0x05,0x16): return 4
    # --- control flow ---
    if b0==0x0f: return {0x00:10,0x05:8,0x06:6,0x01:8}.get(b1)
    # --- fragment sample/deriv/simd helpers ---
    if lo==0x05 and b1==0x80 and b2==0x0c: return 14        # tex sample companion
    if b0==0x37: return 8 if b2==0x56 else 10
    if b0 in (0x38,0x39,0x90,0x92,0xb0,0x18): return 10
    if b0 in (0x47,0xc7): return 10
    if b0==0x17: return 10
    if b0 in (0xbf,0x3f,0xb7) and b2==0x56: return 8
    if b0==0x04 and b1!=0xea: return 8                       # centroid/pos read
    if b0==0x03: return 10                                   # sample-id read
    # --- MESH/OBJECT candidate groups (to be validated by clean tokenization) ---
    if b0==0x54: return 4                                    # mesh preamble marker (Xa71006 seen -> get_sr covers; else 4)
    if b0==0x14: return 4
    if b0==0x33: return 6                                    # low-nibble-3 (mesh count/setup?)
    if b0==0x43:
        # 0x43 00 00 01 = 4B marker; 0x43 00 06 00 ... region prologue tokenizes as 4B
        return 4
    if b0==0x1e: return 8
    if b0==0x6f: return 6
    if b0==0x5c: return 6
    if b0==0x8c: return 4
    if b0==0x84: return 6                                    # seen 84 02 00 10 02 00
    if b0==0x3a: return 4                                    # seen 3a 0c 3c 0e / 3a 06 33
    if b0==0x3c: return 6
    return None

def tok(h):
    b=bytes.fromhex(h.strip()); o=0; out=[]
    while o<len(b):
        L=ilen(b,o)
        if not L or o+L>len(b):
            out.append((o,2,b[o:o+2].hex(),"UNK b0=%02x"%b[o])); o+=2; continue
        out.append((o,L,b[o:o+L].hex(),"%02x"%b[o])); o+=L
    return out

def main():
    path=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),"raw/mains.txt")
    verbose = "-v" in sys.argv
    census={}
    for line in open(path):
        line=line.strip()
        if not line or line.startswith("#"): continue
        p=line.split()
        if len(p)<3: continue
        grp,fn,h = p[0],p[1],p[-1]
        if not all(c in "0123456789abcdef" for c in h.lower()): continue
        recs=tok(h)
        unks=[r for r in recs if r[3].startswith("UNK")]
        b0s={}
        for (o,L,hh,tag) in recs:
            if not tag.startswith("UNK"):
                b0s[tag]=b0s.get(tag,0)+1
        tail = recs[-1][2] if recs else "-"
        print(f"\n===== {grp}/{fn} ({len(h)//2}B) UNK={len(unks)} last={tail} =====")
        print("  byte0:", " ".join(f"{k}x{v}" for k,v in sorted(b0s.items())))
        for k,v in b0s.items(): census[k]=census.get(k,0)+v
        if verbose or unks:
            for (o,L,hh,tag) in recs:
                mark = "  <<<UNK" if tag.startswith("UNK") else ""
                print(f"    @{o:4d} {tag:10s} len={L} {hh}{mark}")
    print("\n===== global byte0 census =====")
    print(" ".join(f"{k}x{v}" for k,v in sorted(census.items())))

if __name__=="__main__":
    main()
