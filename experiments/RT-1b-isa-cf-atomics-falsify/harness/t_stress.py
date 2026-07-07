#!/usr/bin/env python3
# RT-1b item 5: large kernel (deep CF + call + device/tg atomics + spill).
# Tokenize (census: should be ~0 leftover now) + confirm semantics vs CPU ref.
import rt1b, isadb, struct

def w32(x): return ((x + 2**31) % 2**32) - 2**31

def mix(a,b):
    r=w32(a)
    for k in range(8):
        r=w32(w32(w32(r*3)+b) - (r>>1))
        r=w32(r ^ w32(b << (k&3)))
    return r

def lane(x):
    r=[w32(x + k*7 - (k&5)) for k in range(24)]
    for it in range(3):
        for k in range(24):
            r[k]=w32(r[k] + r[(k+1)%24] - (r[(k+7)%24]>>1) + it*k)
    s=0
    for i in range(x & 15):
        if (i&1)==0:
            s = w32(s + r[i]) if i<4 else w32(s - r[i&23])
        else:
            s = w32(s ^ w32(r[(i*3)&23] << 1))
        if s>100000: break
    s=w32(s + mix(x, r[5]))
    acc=0
    for k in range(24): acc=w32(acc+r[k])
    return s, acc

def cpu(a, tgsize):
    out=[0]*len(a)
    for base in range(0, len(a), tgsize):
        grp=range(base, min(base+tgsize, len(a)))
        tg = sum((lane(a[g])[0] & 1) for g in grp)   # threadgroup atomic sum of s&1
        for g in grp:
            s,acc=lane(a[g]); out[g]=w32(acc + s + tg)
    return out

TG=64; N=256
A=[(i*2654435761) & 0x7fffffff for i in range(N)]   # varied inputs
A=[v % 97 for v in A]                                 # keep small-ish
h=rt1b.Harness("kernels/stress.metal","big",workdir=".")
print("main_len", h.main_len)
r=h.run(grid=N,tg=TG,ins={0:rt1b.i32(A)},outs={1:N*4,2:4},tgmem={0:4},timeout=20)
print("status", r["status"], "device counter =", rt1b.di32(r["outs"][2])[0], "(expect", N, ")")
gpu=rt1b.di32(r["outs"][1]); ref=cpu(A,TG)
match=sum(1 for i in range(N) if gpu[i]==ref[i])
print("semantics: %d/%d lanes match CPU reference"%(match,N))
if match!=N:
    for i in range(N):
        if gpu[i]!=ref[i]: print("   first mismatch @%d gpu=%d ref=%d (a=%d)"%(i,gpu[i],ref[i],A[i])); break
# determinism
r2=h.run(grid=N,tg=TG,ins={0:rt1b.i32(A)},outs={1:N*4,2:4},tgmem={0:4},timeout=20)
print("determinism:", "identical" if rt1b.di32(r2["outs"][1])==gpu else "DIFFERS")

print("\n### CENSUS of big _agc.main")
b=h.main
# (a) strict tokenizer: leftover at first undecodable instruction
recs,leftover=isadb.disassemble(b)
print("  strict isadb.disassemble: %d instrs, %d leftover bytes (%.1f%% covered)"%(
    len(recs), len(leftover), 100*(len(b)-len(leftover))/len(b)))
# (b) resync census: coverage and undecoded byte0 histogram
off=0; covered=0; unk={}
while off < len(b):
    try: rec,ln=isadb.decode_one(b,off)
    except Exception: rec,ln=None,None
    if ln and rec and not rec.get("error"):
        covered+=ln; off+=ln
    else:
        unk[b[off]]=unk.get(b[off],0)+1; off+=2
print("  resync census: %.1f%% of bytes decoded"%(100*covered/len(b)))
if unk:
    print("  undecoded byte0 leaders (resync): "+", ".join("%#04x×%d"%(k,v) for k,v in sorted(unk.items())))
