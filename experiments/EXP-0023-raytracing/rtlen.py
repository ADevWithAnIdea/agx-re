#!/usr/bin/env python3
# EXP-0023 iterative length finder. Start from the VALIDATED tools/agx-isa length
# rule (isadb.instr_length) and add candidate ray-tracing group lengths (RT_LEN).
# Report the first offset that fails to tokenize so we can add one group at a time
# until a whole RT _agc.main tokenizes with zero leftover (the ISA-bringup method).
# CLEAN-ROOM: OUR OWN compiled bytes only.
import sys
sys.path.insert(0,'/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

def B(b,o): return b[o] if 0<=o<len(b) else -1

# Candidate RT / not-yet-in-DB group lengths, keyed by byte0 or a predicate.
def rt_len(b,o):
    b0=b[o]; lo=b0&0x0f
    # --- the novel RT intersect/setup group: byte0 low-nibble 0x4 (high nibble=dst reg) ---
    if lo==0x4:
        return 8
    # --- dedicated AS/ray-data load group 0xdf (memory-family sibling, 14B like 0x67) ---
    if b0==0xdf:
        return 14
    # --- native-half 2-source ALU 0x10 (sibling of 0x11), same length bit as 0x09/0x11 ---
    if b0==0x10:
        return 8 if (B(b,o+2)&0x02) else 6
    # --- vtx/frag memory variants 0x07/0x87/0x97/0xa7 seen in EXP-0008 (not RT) ---
    if b0 in (0x07,0x87,0x97):
        return 6
    # --- low-nibble-0xf memory-family siblings (0x5f, ...) with byte+2 in {0x54,0x56}: 14 ---
    if lo==0xf and B(b,o+2) in (0x54,0x56):
        return 14
    # --- RT transform/test op: low-nibble-0x2 with byte+2==0x27 (X2 YY 27 81 ...): 10 ---
    if lo==0x2 and B(b,o+2)==0x27:
        return 10
    return None

def L(b,o):
    b0=b[o]; lo=b0&0x0f
    # RT-specific overrides FIRST (isadb mis-lengths some of these):
    # The low-nibble-0xb group: 10-byte funary/ilogic have op byte+2 in {0x0e,0x1e,0x1f};
    # every other byte+2 is a 4-byte move variant (uniform 0x01, RT-special 0x81, 0x80, 0x00).
    if lo==0x0b:
        return 10 if B(b,o+2) in (0x0e,0x1e,0x1f) else 4
    if lo==0x4: return 8                              # RT intersect/setup group (X4)
    if b0==0xdf: return 14                            # dedicated AS/ray-data load
    if b0==0x10: return 8 if (B(b,o+2)&0x02) else 6   # native-half 2-src ALU
    if b0 in (0x07,0x87,0x97): return 6
    v=isadb.instr_length(b,o)
    if v is not None: return v
    return rt_len(b,o)

def tok(b):
    o=0; recs=[]
    while o<len(b):
        Lv=L(b,o)
        if Lv is None or o+Lv>len(b):
            return recs,o
        recs.append((o,b[o],Lv)); o+=Lv
    return recs,None

def main():
    path=sys.argv[1] if len(sys.argv)>1 else 'raw/mains.txt'
    want=[a for a in sys.argv[2:] if not a.startswith('-')]
    verbose='-v' in sys.argv
    for line in open(path):
        line=line.strip()
        if not line or line.startswith('#'): continue
        p=line.split(); grp,fn,h=p[0],p[1],p[-1]
        if want and fn not in want: continue
        if not all(c in '0123456789abcdef' for c in h.lower()): continue
        b=bytes.fromhex(h); recs,fail=tok(b)
        if fail is None:
            hist={}
            rtcount=0; dfcount=0; backj=0
            for o,b0,Lv in recs:
                hist[b0]=hist.get(b0,0)+1
                if (b0&0x0f)==0x4: rtcount+=1
                if b0==0xdf: dfcount+=1
                if b0==0x0f and Lv==10 and b[o+1]==0x00 and b[o+2]==0x54:
                    off=int.from_bytes(b[o+3:o+8],'little',signed=True)
                    if off<0: backj+=1
            print(f"{fn:16s} {len(b):5d}B CLEAN {len(recs)} instrs | RT(0x?4)={rtcount} 0xdf={dfcount} backjumps={backj}")
            if verbose:
                for o,b0,Lv in recs:
                    mark=' <<RT' if (b0&0x0f)==0x4 else (' <<AS' if b0==0xdf else '')
                    print(f"   @{o:4d} {b0:#04x} L={Lv:2d} {b[o:o+Lv].hex()}{mark}")
        else:
            print(f"{fn:16s} {len(b):5d}B FAIL@{fail} {b[fail]:#04x}: {b[fail:fail+16].hex()}")
if __name__=='__main__': main()
PY = None
