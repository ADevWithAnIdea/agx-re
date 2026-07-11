import sys, os, glob, collections
# reuse census.py's isadb locator + walk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec = importlib.util.spec_from_file_location("cen", os.path.join(os.path.dirname(os.path.abspath(__file__)),"census.py"))
# instead of importing census (runs main), just re-add isadb path and reuse functions
for cand in ("../tools/agx-isa","tools/agx-isa","/Users/user/cleanroom_work/tools/agx-isa"):
    if os.path.isfile(os.path.join(cand,"isadb.py")): sys.path.insert(0,cand); break
import isadb
def trim(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]
def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError: return L,None
def first_desync(buf):
    off=0;n=len(buf)
    while off<n:
        L,mn=named_at(buf,off,n)
        if L is not None and mn is not None: off+=L; continue
        if L is not None and mn is None:  # length-only, treat as covered
            off+=L; continue
        return off,buf[off]  # undecoded start
    return None,None
files=sorted(glob.glob("hex/*.hex"))
fd=collections.Counter(); ctx=collections.defaultdict(list); clean=0; seen=set(); total=0
for f in files:
    h=open(f).read().strip()
    if not h: continue
    b=trim(bytes.fromhex(h))
    if not b: continue
    import hashlib; hh=hashlib.sha256(b).hexdigest()
    if hh in seen: continue
    seen.add(hh); total+=1
    off,b0=first_desync(b)
    if off is None: clean+=1; continue
    fd[b0]+=1
    if len(ctx[b0])<3: ctx[b0].append(b[off:off+6].hex(' '))
print(f"unique kernels: {total}")
print(f"FULLY DECODE on M5 with G17P DB (no desync): {clean} ({100*clean/total:.1f}%)")
print(f"kernels with >=1 desync: {total-clean}")
print("\nFIRST-DESYNC byte0 (root-cause diverged ops, ranked):")
print("byte0 | #kernels-first-break-here | sample 6-byte contexts")
for b0,c in fd.most_common(30):
    print(f"  0x{b0:02x} | {c:5d} | " + "   ".join(ctx[b0]))
