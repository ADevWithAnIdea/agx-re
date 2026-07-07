#!/usr/bin/env python3
# EXP-0038 analysis harness (device-side). Compile OUR OWN MSL, extract _agc.main,
# resync-tokenize with the merged tools/agx-isa DB, and print per-op detail so the
# undecoded pack/carry/frame ops can be located and bit-decoded.
#
# CLEAN-ROOM: only our own compiled shader bytes are inspected. Reuses shdump +
# agxparse (OWN-SHADER tools) + isadb (READ-ONLY encoding DB).
import sys, os, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # isadb.py, agxparse.py live alongside on the device
import isadb

SHDUMP = os.path.join(HERE, 'shdump')
AGXPARSE = os.path.join(HERE, 'agxparse.py')

def compile_extract(src, fn, nofast=False):
    """Compile one kernel from src, return _agc.main bytes."""
    binf = os.path.join(tempfile.gettempdir(), f'exp38_{fn}.bin')
    cmd = [SHDUMP, '-o', binf, '-f', fn]
    if nofast: cmd.append('--no-fast-math')
    cmd.append(src)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'shdump {fn} failed: {r.stderr[-400:]}')
    loc = subprocess.run([sys.executable, AGXPARSE, binf, '--locate', '_agc.main'],
                         capture_output=True, text=True)
    if loc.returncode != 0 or not loc.stdout.strip():
        raise RuntimeError(f'locate {fn} failed: {loc.stderr[-400:]}')
    off, ln = [int(x, 0) for x in loc.stdout.split()[:2]]
    with open(binf, 'rb') as f:
        f.seek(off); data = f.read(ln)
    return data

def trim(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def walk(buf):
    recs, off, n = [], 0, len(buf)
    while off < n:
        b0 = buf[off]
        L, mn = named_at(buf, off, n)
        if L is not None:
            recs.append((off, b0, L, mn, 'named' if mn else 'length_only'))
            off += L; continue
        start = off; off += 2
        while off < n:
            _, mn2 = named_at(buf, off, n)
            if mn2 is not None: break
            off += 2
        recs.append((start, b0, off - start, None, 'undecoded'))
    return recs

def show(name, buf, focus=None):
    buf = trim(buf)
    print(f'\n===== {name}  ({len(buf)} bytes) =====')
    print('  raw:', buf.hex())
    for (off, b0, L, mn, st) in walk(buf):
        chunk = buf[off:off+L]
        b2 = buf[off+2] if off+2 < len(buf) else -1
        tag = mn if mn else ('LEN?' if st=='length_only' else 'UNDECODED')
        mark = ''
        if focus and b0 in focus:
            mark = '   <<< FOCUS'
        print(f'  +{off:#05x} b0={b0:#04x} b2={b2:#04x} len={L:2d} {st:11s} {tag:14s} {chunk.hex()}{mark}')

def main():
    # (source, [functions], focus-byte0-set)
    jobs = [
        ('kernels/halfpack.metal',
         ['k_h1add','k_h2add','k_h2mul','k_h4add','k_packh2','k_unpackh2','k_h2roundtrip','k_h2fma'],
         {0x10,0x18,0x30,0x38,0x11}),
        ('kernels/u64carry.metal',
         ['k_u32add','k_u64add','k_u64sub','k_u64addk','k_u64add3','k_i64add'],
         {0x32,0x9f,0x1f}),
        ('kernels/frame.metal',
         ['k_leaf','k_chain','k_deep'],
         {0x6f,0x07,0x43,0x73,0x8f}),
        ('kernels/cachebit.metal',
         ['k_reduce1','k_reduce2','k_reduce_two','k_scan','k_unpack1','k_unpack2'],
         {0xbf,0x3f,0x17,0xb7}),
    ]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for src, fns, focus in jobs:
        if only and only not in src: continue
        for fn in fns:
            try:
                b = compile_extract(os.path.join(HERE, src), fn)
                show(f'{os.path.basename(src)}::{fn}', b, focus)
            except Exception as e:
                print(f'\n===== {src}::{fn}  ERROR: {e}')

if __name__ == '__main__':
    main()
