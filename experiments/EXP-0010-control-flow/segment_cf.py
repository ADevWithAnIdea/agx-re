#!/usr/bin/env python3
# segment_cf.py -- host-side. Segment specific control-flow programs with refined
# hypotheses for the control ops, and compute the backward-jump target to pin the
# relative base. CLEAN-ROOM: our own compiled bytes only.

PROG = {
 "eret4":   "0ca010060a01228214220f0554211c07e7005402000021005100009011000f06040100000e000000",
 "gsel4":   "1ca010060203078422ef0522a0dee7005400000121001100009011000e000000",
 "dsel5":   "1ca01006671044000101200051010040460002010f8422e416c2a0c8e7005400000121001100009011000e000000",
 "prodloop":"0ca0100667104404010020005101004046000a85228006c21c812200000000000f0554010f0154560000000000001c812200000000003b0020000f05541a9f0104060302188815040a0723050600070000009f015402030408e816059f0154020202088815048f0454220f0054d4ffffffffff000f06040200000f0604010000e7005402000021001100009011000e000000",
 "cont":    "0ca01006671044020100200051010040460 0".replace(" ",""),
}
# fill cont properly
PROG["cont"]="0ca01006671044020100200051010040460 0a832380060007c200002b0020000f0554210f0154520000000000003b0020000f05541a62872780278016020086000000019f0154060302188815040a0723030600070000009f015404021810a817058f0454220f0054d0ffffffffff000f06040200000f0604010000e7005404000021001100009011000e000000".replace(" ","")

def klen(b,o):
    b0=b[o]; lo=b0&0x0f
    if b0==0x0e: return 4
    if lo==0x0c: return 4
    if b0 in (0x67,0xe7): return 14
    if lo==0x09: return 8 if (o+2<len(b) and b[o+2]&2) else 6
    if b0 in (0x9f,0x1f,0xa7): return 10 if (o+1<len(b) and b[o+1]&1) else 12
    if b0==0x27: return 8
    if b0==0x02: return 6
    if b0==0x12: return 14 if (o+2<len(b) and (b[o+2]&0xf)==0xd) else 6
    # ---- control-flow hypotheses (EXP-0010) ----
    if b0==0x0a: return 6                     # compare -> predicate
    if b0==0x16 or b0==0x05: return 4         # select
    if b0==0x3b: return 10                    # (loop-related, seen in cont/prodloop)
    if b0==0x8f: return 4                     # (loop tail op)
    if b0==0x0f:
        sub=b[o+1] if o+1<len(b) else 0
        if sub==0x00: return 10               # jump: 0f 00 54 <off6> 00
        if sub in (0x05,0x01): return 4       # mask push/else: 0f 05 54 / 0f 01 54
        if sub==0x06: return 6                # reconverge/pop: 0f 06 04 xx 00 00
        if sub==0x04: return 4
        return 4
    if b0==0x1c: return 4                     # mov-imm / get-sr-like
    return None

def seg(name,h):
    b=bytes.fromhex(h); o=0; out=[]
    while o<len(b):
        L=klen(b,o)
        if L is None:
            out.append((o,None,b[o:o+2].hex()));
            print(f"{name}: STUCK at {o} byte0={b[o]:#04x} rest={b[o:].hex()}"); return
        out.append((o,L,b[o:o+L].hex())); o+=L
    print(f"\n=== {name} ({len(b)}B) ===")
    for (o,L,hx) in out:
        b0=b[o]
        tag=""
        if b0==0x0f and b[o+1]==0x00:
            off=int.from_bytes(b[o+3:o+9],"little")
            if off>=(1<<47): off-=(1<<48)
            tgt_from_start=o+off; tgt_from_end=o+L+off
            tag=f"  JUMP off={off}  target(from start)={tgt_from_start} target(from end)={tgt_from_end}"
        print(f"  [{o:3d} +{L}] {hx}{tag}")

for n,h in PROG.items(): seg(n,h)
