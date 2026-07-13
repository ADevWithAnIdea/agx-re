import sys, glob, hashlib, signal, time
FORK=sys.argv[1]; sys.path.insert(0,FORK)
import isadb
class TO(Exception): pass
def _h(*a): raise TO()
signal.signal(signal.SIGALRM,_h)
def trim(b):
    e=len(b)
    while e>=2 and b[e-2:e]==b'\x06\x00': e-=2
    return b[:e]
def walk(b):
    lt=ln=ll=lu=0; off=0; n=len(b)
    while off<n:
        L=isadb.instr_length(b,off)
        if L is None or off+L>n:
            st=off; off+=2
            while off<n:
                L2=isadb.instr_length(b,off)
                if L2 is not None and off+L2<=n: break
                off+=2
            lu+=off-st; lt+=off-st
        else:
            try: mn=isadb.decode_one(b,off)[0].get('mnemonic')
            except Exception: mn=None
            if mn: ln+=L
            else: ll+=L
            lt+=L; off+=L
    return lt,ln,ll,lu
def census(hexdir, budget=45):
    t0=time.time(); tot=named=lo=ud=0; seen=set(); skip=0; nf=0; hf=[]
    for f in sorted(glob.glob(hexdir+"/*.hex")):
        if time.time()-t0>budget: break
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h))
        if not b: continue
        hh=hashlib.sha256(b).hexdigest()
        if hh in seen: continue
        seen.add(hh)
        signal.setitimer(signal.ITIMER_REAL,3)
        try:
            lt,ln,ll,lu=walk(b); signal.setitimer(signal.ITIMER_REAL,0)
            tot+=lt;named+=ln;lo+=ll;ud+=lu;nf+=1
        except TO:
            signal.setitimer(signal.ITIMER_REAL,0); skip+=1
            if len(hf)<6: hf.append(f.split('/')[-1])
    return len(seen),tot,named,lo,ud,nf,skip,hf
for nm,d in [("own","/Users/user/cleanroom_work/EXP-M5-02/hex"),("tp","/Users/user/cleanroom_work/EXP-M5-03/tp_hex")]:
    u,tot,named,lo,ud,nf,skip,hf=census(d)
    if tot: print(f"{nm}: {nf}f scanned (skip-hang {skip}) | named {100*named/tot:.2f}% | UNDEC {100*ud/tot:.2f}% | byte-cov {100*(named+lo)/tot:.2f}%")
    if hf: print(f"   HANG files: {hf}")
