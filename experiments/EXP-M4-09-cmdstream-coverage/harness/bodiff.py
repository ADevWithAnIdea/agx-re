#!/usr/bin/env python3
"""bodiff.py -- byte/word diff of iotrace BO snapshots across two captures.

Part of EXP-0011 (Phase 2 cmdstream decode). The change-one-parameter method:
capture the registered GPU BOs with parameter set A, again with set B, and diff
to localise which descriptor bytes encode the parameter that changed.

Two modes:
  * two files:  bodiff.py A.hex B.hex
  * two dirs :  bodiff.py DIR_A DIR_B [--va 0x100000b0000] [--maxlen 0x80]
                pairs BOs by gpu_va (the allocator is deterministic across runs);
                --va restricts to one BO; --maxlen limits how far in to compare.

CLEAN-ROOM: DATA only. No Apple code inspected.
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va = cpu = size = 0
    data = bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m = HDR.search(line)
                if m: gpu_va, cpu, size = (int(m.group(i), 16) for i in (1, 2, 3))
                continue
            m = HEXLINE.match(line)
            if not m: continue
            off = int(m.group(1), 16)
            b = bytes.fromhex(m.group(2).replace(' ', ''))
            if len(data) < off + len(b):
                data.extend(b'\x00' * (off + len(b) - len(data)))
            data[off:off+len(b)] = b
    return {'path': path, 'gpu_va': gpu_va, 'cpu': cpu, 'size': size, 'data': bytes(data)}

def diff_pair(A, B, maxlen=None, label=''):
    da, db = A['data'], B['data']
    n = min(len(da), len(db))
    if maxlen: n = min(n, maxlen)
    diffs = []
    for off in range(0, n, 4):
        wa = da[off:off+4]; wb = db[off:off+4]
        if wa != wb:
            va = int.from_bytes(wa.ljust(4, b'\0'), 'little')
            vb = int.from_bytes(wb.ljust(4, b'\0'), 'little')
            diffs.append((off, va, vb))
    if diffs or len(da) != len(db):
        hdr = label or f"gpu_va={A['gpu_va']:#x}"
        print(f"\n=== {hdr}  A={os.path.basename(A['path'])}  B={os.path.basename(B['path'])} ===")
        if len(da) != len(db):
            print(f"  [size differs: A read {len(da):#x}  B read {len(db):#x}]")
        for off, va, vb in diffs:
            print(f"  +{off:#06x}: {va:#010x} -> {vb:#010x}   (A {va}  B {vb})")
    return len(diffs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--va', default=None, help='restrict dir-mode to this gpu_va')
    ap.add_argument('--maxlen', default=None, help='limit compare length (hex ok)')
    args = ap.parse_args()
    maxlen = int(args.maxlen, 0) if args.maxlen else None

    if os.path.isfile(args.a) and os.path.isfile(args.b):
        diff_pair(load(args.a), load(args.b), maxlen)
        return 0

    # dir mode: pair by gpu_va
    A = {}
    for p in glob.glob(os.path.join(args.a, '*.hex')):
        b = load(p);  A.setdefault(b['gpu_va'], b)
    B = {}
    for p in glob.glob(os.path.join(args.b, '*.hex')):
        b = load(p);  B.setdefault(b['gpu_va'], b)
    only_a = sorted(set(A) - set(B))
    only_b = sorted(set(B) - set(A))
    if only_a: print("BOs only in A:", ' '.join(f'{v:#x}' for v in only_a))
    if only_b: print("BOs only in B:", ' '.join(f'{v:#x}' for v in only_b))
    vas = [int(args.va, 0)] if args.va else sorted(set(A) & set(B))
    total = 0
    for va in vas:
        if va in A and va in B:
            total += diff_pair(A[va], B[va], maxlen)
    print(f"\n[{total} differing words across {len(vas)} paired BO(s)]")
    return 0

if __name__ == '__main__':
    sys.exit(main())
