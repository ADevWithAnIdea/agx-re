#!/usr/bin/env python3
# propose.py — for a kernel bin, walk with the DB; where the DB gives no length
# (or lands mid-stream), try candidate lengths {2,4,6,8,10,12,14,16} and pick the
# SMALLEST that lands on a byte0 the DB can length (a "known" op), preferring one
# that also chains forward a few steps. Reports the proposed boundary chain.
# This is a HEURISTIC to expose likely true boundaries; every proposal is then
# cross-checked and splice-validated. CLEAN-ROOM: our own shader bytes only.
import sys
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
sys.path.insert(0, '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census')
import isadb, agxparse

# ---- confirmed fixes applied as an override layer (before we edit isadb.py) ----
_orig_len = isadb.instr_length
def _bat(buf,off,k): return buf[off+k] if off+k<len(buf) else -1
def _patched(buf, off=0):
    b0=buf[off]
    if b0==0x02:
        return 8 if (_bat(buf,off,1)&0x80) else 6   # 0x02 long form: byte1 bit7 set
    return _orig_len(buf,off)
isadb.instr_length = _patched

def trim(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]

def known_len(buf, off):
    """DB length if it lands within buffer, else None."""
    if off>=len(buf): return None
    L=isadb.instr_length(buf,off)
    if L is None or off+L>len(buf): return None
    return L

def chains(buf, off, depth):
    """True if from off we can take `depth` DB-known steps without falling off."""
    for _ in range(depth):
        L=known_len(buf,off)
        if L is None: return False
        off+=L
        if off==len(buf): return True
    return True

def load(binpath, stage='compute'):
    buf=open(binpath,'rb').read()
    _,st=agxparse.extract_all_stages(buf)
    return trim(st[stage]['_agc.main'])

def walk_propose(b):
    n=len(b); off=0; idx=0; out=[]
    while off<n:
        b0=b[off]
        L=known_len(b,off)
        if L is not None:
            try: rec,_=isadb.decode_one(b,off); mn=rec['mnemonic']
            except ValueError: mn='?'
            out.append((idx,off,L,'DB',mn,b[off:off+L].hex(' ')))
            off+=L; idx+=1; continue
        # unknown: propose smallest length landing on a known op that chains >=2
        best=None
        for cand in (2,4,6,8,10,12,14,16):
            if off+cand>n: break
            if off+cand==n:
                best=cand; break
            nb0=b[off+cand]
            nl=known_len(b,off+cand)
            if nl is not None and chains(b,off+cand,2):
                best=cand; break
        if best is None:
            # fallback: smallest landing on any known-length position
            for cand in (2,4,6,8,10,12,14,16):
                if off+cand>n: break
                if known_len(b,off+cand) is not None:
                    best=cand; break
        if best is None: best=2
        out.append((idx,off,best,'PROP',f'0x{b0:02x}?',b[off:off+best].hex(' ')))
        off+=best; idx+=1
    return out

if __name__=='__main__':
    binp=sys.argv[1]; stage=sys.argv[2] if len(sys.argv)>2 else 'compute'
    b=load(binp,stage)
    print(f"=== {binp} ({len(b)} bytes) ===")
    for idx,off,L,src,mn,hx in walk_propose(b):
        tag='   ' if src=='DB' else '>>>'
        print(f"{tag}[{idx:3d}] @{off:4d} L={L:2d} {src:4s} {mn:16s} {hx}")
