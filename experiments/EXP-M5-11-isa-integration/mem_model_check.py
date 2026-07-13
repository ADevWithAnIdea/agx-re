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
# Count occurrences of A18 memory ops (device_load 0x67, device_store 0xe7) vs M5 split
# (m5_addr_gen, m5_load, m5_store, m5_store_ext) across the corpus.
for label,d in [("own","/Users/user/cleanroom_work/EXP-M5-02/hex"),("tp","/Users/user/cleanroom_work/EXP-M5-03/tp_hex")]:
    mn_ct=collections.Counter(); seen=set(); t0=time.time(); files=0
    for f in sorted(glob.glob(d+"/*.hex")):
        if time.time()-t0>45: break
        h=open(f).read().strip()
        if not h: continue
        b=trim(bytes.fromhex(h))
        if not b: continue
        hh=hashlib.sha256(b).hexdigest()
        if hh in seen: continue
        seen.add(hh); files+=1
        off=0;n=len(b)
        signal.setitimer(signal.ITIMER_REAL,3)
        try:
            while off<n:
                L=isadb.instr_length(b,off)
                if L is None or off+L>n:
                    off+=2
                    while off<n:
                        L2=isadb.instr_length(b,off)
                        if L2 is not None and off+L2<=n: break
                        off+=2
                    continue
                try: mn=isadb.decode_one(b,off)[0].get('mnemonic')
                except Exception: mn=None
                if mn in ('device_load','device_store','atomic_rmw','atomic_mem','atomic_tg',
                          'm5_addr_gen','m5_load','m5_load_compact','m5_store','m5_store_ext',
                          'm5_reduce','m5_shuffle','m5_iadd','m5_alu'):
                    mn_ct[mn]+=1
                off+=L
            signal.setitimer(signal.ITIMER_REAL,0)
        except TO: signal.setitimer(signal.ITIMER_REAL,0)
    print(f"=== {label} ({files} files): memory-model + M5 op counts ===")
    for k in ['device_load','device_store','atomic_rmw','atomic_mem','atomic_tg',
              'm5_addr_gen','m5_load','m5_load_compact','m5_store','m5_store_ext',
              'm5_reduce','m5_shuffle','m5_iadd','m5_alu']:
        print(f"   {k:16s} {mn_ct.get(k,0)}")
