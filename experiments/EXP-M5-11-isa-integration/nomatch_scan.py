import sys, glob, hashlib, signal, time, collections
FORK=sys.argv[1]; sys.path.insert(0,FORK)
import isadb
class TO(Exception): pass
def _h(*a): raise TO()
signal.signal(signal.SIGALRM,_h)
def trim(b):
    e=len(b)
    while e>=2 and b[e-2:e]==b'\x06\x00': e-=2
    return b[:e]
def scan(b, nmctr, bytescnt):
    off=0; n=len(b)
    while off<n:
        L=isadb.instr_length(b,off)
        if L is None or off+L>n:
            st=off; off+=2
            while off<n:
                L2=isadb.instr_length(b,off)
                if L2 is not None and off+L2<=n: break
                off+=2
        else:
            try: mn=isadb.decode_one(b,off)[0].get('mnemonic')
            except Exception: mn=None
            if not mn:
                sig=(L, b[off:off+3].hex())
                nmctr[sig]+=1
                bytescnt[sig]+=L
            off+=L
for label,d in [("own","/Users/user/cleanroom_work/EXP-M5-02/hex"),("tp","/Users/user/cleanroom_work/EXP-M5-03/tp_hex")]:
    nmctr=collections.Counter(); bytescnt=collections.Counter(); seen=set(); t0=time.time()
    for f in sorted(glob.glob(d+"/*.hex")):
        if time.time()-t0>40: break
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h))
        if not b: continue
        hh=hashlib.sha256(b).hexdigest()
        if hh in seen: continue
        seen.add(hh)
        signal.setitimer(signal.ITIMER_REAL,3)
        try: scan(b,nmctr,bytescnt); signal.setitimer(signal.ITIMER_REAL,0)
        except TO: signal.setitimer(signal.ITIMER_REAL,0)
    print(f"==== {label}: top NOMATCH (length, byte0..2) by BYTES ====")
    for sig,c in bytescnt.most_common(24):
        print(f"   L={sig[0]:<3} {sig[1]:6s}  x{nmctr[sig]:<4} = {c} bytes")
