#!/usr/bin/env python3
# EXP-0038: compile one kernel and dump+tokenize EVERY symbol region (incl.
# out-of-line helper subroutines -- where the non-leaf 0x6f frame prologue lives).
# CLEAN-ROOM: only our own compiled bytes. Reuses shdump + agxparse + isadb.
import sys, os, subprocess, tempfile, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isadb
SHDUMP = os.path.join(HERE, 'shdump'); AGXPARSE = os.path.join(HERE, 'agxparse.py')

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n: return None, None
    try:
        rec, _ = isadb.decode_one(buf, off); return L, rec['mnemonic']
    except ValueError: return L, None

def walk_print(buf):
    off, n = 0, len(buf)
    while off < n:
        b0 = buf[off]; L, mn = named_at(buf, off, n)
        if L is not None:
            b2 = buf[off+2] if off+2 < n else -1
            print(f'    +{off:#05x} b0={b0:#04x} b2={b2:#04x} len={L:2d} {"named " if mn else "LEN?  "} {mn or "":14s} {buf[off:off+L].hex()}')
            off += L; continue
        start = off; off += 2
        while off < n:
            _, mn2 = named_at(buf, off, n)
            if mn2 is not None: break
            off += 2
        print(f'    +{start:#05x} b0={b0:#04x}          len={off-start:2d} UNDECODED      {buf[start:off].hex()}')

def main():
    src = os.path.join(HERE, sys.argv[1]); fn = sys.argv[2]
    binf = os.path.join(tempfile.gettempdir(), f'reg_{fn}.bin')
    rc, o, e = sh([SHDUMP, '-o', binf, '-f', fn, src])
    if rc: print('shdump failed:', e[-300:]); return
    rc, o, e = sh([sys.executable, AGXPARSE, binf, '--json'])
    rep = json.loads(o)
    stages = rep.get('stages', {})
    for sname, a in stages.items():
        print(f'== stage {sname}: __text {a.get("whole_text_length")}B, regions:')
        for (name, start, end, length) in a.get('regions', []):
            print(f'  region {name} [{start}:{end}] {length}B')
            rc2, hx, e2 = sh([sys.executable, AGXPARSE, binf, '--symbol', name, '--extract-hex'])
            if rc2 or not hx.strip():
                print('    (no hex)'); continue
            b = bytes.fromhex(hx.strip())
            # trim trailing 06 00 padding
            while len(b) >= 2 and b[-2:] == b'\x06\x00': b = b[:-2]
            print('    raw:', b.hex())
            walk_print(b)

if __name__ == '__main__':
    main()
