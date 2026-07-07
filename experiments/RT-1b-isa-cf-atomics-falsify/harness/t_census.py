#!/usr/bin/env python3
# RT-1b: alignment-preserving census. Walk using instr_length (advance by known
# length even when no descriptor matches) so we distinguish REAL DB gaps
# (length known but unnamed, or length unknown at an aligned boundary) from
# resync noise. Reports where the strict tokenizer FIRST halts.
import rt1b, isadb

def census(name, src, fn):
    h=rt1b.Harness(src, fn, workdir=".")
    b=h.main; off=0
    named=0; lenonly=0; unklen=0
    lo_hist={}; uk_hist={}; first_halt=None
    while off < len(b):
        L=isadb.instr_length(b, off)
        if L is None or L==0:
            if first_halt is None: first_halt=(off, b[off], b[off:off+8].hex())
            uk_hist[b[off]]=uk_hist.get(b[off],0)+1
            off+=2; unklen+=2; continue
        # length known; does a descriptor match?
        try:
            rec,_=isadb.decode_one(b,off); ok = rec and not rec.get("error")
        except Exception:
            ok=False
        if ok: named+=L
        else:
            if first_halt is None: first_halt=(off, b[off], b[off:off+L].hex())
            lenonly+=L; lo_hist[b[off]]=lo_hist.get(b[off],0)+1
        off+=L
    tot=len(b)
    print("== %s (%s)  main_len=%d"%(fn,src,tot))
    print("   named(desc)   : %5d B  %.1f%%"%(named,100*named/tot))
    print("   length-only   : %5d B  %.1f%%  (aligned, known length, NO descriptor)"%(lenonly,100*lenonly/tot))
    print("   unknown-length: %5d B  %.1f%%  (no length rule -> 2B resync)"%(unklen,100*unklen/tot))
    print("   FIRST strict halt @+0x%x byte0=%#04x : %s"%(first_halt if first_halt else (0,0,'-')))
    if lo_hist: print("   length-only byte0: "+", ".join("%#04x×%d"%(k,v) for k,v in sorted(lo_hist.items())))
    if uk_hist: print("   unknown-len byte0: "+", ".join("%#04x×%d"%(k,v) for k,v in sorted(uk_hist.items())))
    return lo_hist, uk_hist

census("stress","kernels/stress.metal","big")
print()
# check DB coverage of the two prominent leaders
for b0 in (0x0f, 0x32):
    present = any((d.get("match") and d["match"][0][2]==b0) or
                  any(m[0]==0 and m[2]==b0 for m in d.get("match",[])) for d in isadb.DB)
    print("DB has a descriptor matching byte0=%#04x ? %s"%(b0, present))
