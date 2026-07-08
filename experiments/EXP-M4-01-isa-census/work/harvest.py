#!/usr/bin/env python3
# harvest.py — iterative ground-truth boundary harvester over the whole corpus.
# Uses solve.anchor() for trusted anchors; bootstraps a (sig->length) map from
# gaps that tile UNIQUELY. sig = (b0&0x0f, b2). Iterates to convergence, then
# reports any (sig) that appears with a UNIQUE resolved length across the corpus,
# plus remaining ambiguous gaps. CLEAN-ROOM: our own shader bytes only.
import sys, os, glob, collections
sys.path.insert(0,'/Users/user/cleanroom_gpu/tools/agx-isa')
sys.path.insert(0,'/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census')
import solve

HEXDIR='/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex'
A18DIR='/Users/user/cleanroom_gpu/experiments/EXP-0036-consolidation-census/hex'

def load_hex(path):
    return solve.trim(bytes.fromhex(open(path).read().strip()))

def all_streams(hexdir):
    seen=set(); out=[]
    for f in sorted(glob.glob(os.path.join(hexdir,'*.hex'))):
        h=open(f).read().strip()
        if not h: continue
        b=solve.trim(bytes.fromhex(h))
        hh=hash(b)
        if hh in seen: continue
        seen.add(hh); out.append((os.path.basename(f)[:-4], b))
    return out

def tile_gap(b,start,end,hyp):
    return solve.tile(b,start,end,hyp)

def gaps_of(b):
    """Return list of (start,end) gaps between anchors (and the anchor list)."""
    n=len(b); off=0; gaps=[]
    while off<n:
        a=solve.anchor(b,off)
        if a: off+=a[0]; continue
        probe=off+2; nxt=None
        while probe<=n:
            if probe==n or solve.anchor(b,probe): nxt=probe; break
            probe+=2
        if nxt is None: nxt=n
        gaps.append((off,nxt)); off=nxt
    return gaps

def harvest(streams, hyp, rounds=6):
    for r in range(rounds):
        sig_lengths=collections.defaultdict(set)   # sig -> set of lengths seen in UNIQUE tilings
        for name,b in streams:
            for (s,e) in gaps_of(b):
                tl=tile_gap(b,s,e,hyp)
                if len(tl)==1:
                    for (o,L) in tl[0]:
                        sig=(b[o]&0x0f, solve.B(b,o,2))
                        sig_lengths[sig].add(L)
        # add sigs that resolve to exactly one length AND aren't in hyp yet
        added=0
        for sig,ls in sig_lengths.items():
            if sig not in hyp and len(ls)==1:
                hyp[sig]=next(iter(ls)); added+=1
        if added==0: break
    return hyp

def report(streams, hyp):
    amb=0; solved=0; ambsigs=collections.Counter()
    total_gaps=0
    for name,b in streams:
        for (s,e) in gaps_of(b):
            total_gaps+=1
            tl=tile_gap(b,s,e,hyp)
            if len(tl)==1: solved+=1
            else:
                amb+=1
                # record the leading sig of the ambiguous gap
                ambsigs[(b[s]&0x0f, solve.B(b,s,2), e-s)]+=1
    return solved, amb, total_gaps, ambsigs

if __name__=='__main__':
    which = sys.argv[1] if len(sys.argv)>1 else 'm4'
    streams = all_streams(HEXDIR if which=='m4' else A18DIR)
    hyp={}
    hyp=harvest(streams,hyp)
    solved,amb,tot,ambsigs=report(streams,hyp)
    print(f"[{which}] gaps: {solved} unique / {amb} ambiguous / {tot} total")
    print(f"harvested {len(hyp)} signature->length rules")
    # print harvested sigs grouped by b0 low-nibble
    bygroup=collections.defaultdict(list)
    for (ln,b2),L in sorted(hyp.items()):
        bygroup[ln].append((b2,L))
    for ln in sorted(bygroup):
        items=', '.join(f'b2={b2:02x}->{L}' for b2,L in sorted(bygroup[ln]))
        print(f"  b0lo={ln:x}: {items}")
    print("--- top ambiguous gaps (b0lo/b2/size): ---")
    for (ln,b2,sz),c in ambsigs.most_common(20):
        print(f"  b0lo={ln:x} b2={b2:02x} size={sz}: {c}")
