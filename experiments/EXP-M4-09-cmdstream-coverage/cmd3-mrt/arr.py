#!/usr/bin/env python3
"""arr.py — load an iotrace BO .hex snapshot and dump/inspect the MRT color-descriptor
array in the tiler geometry heap (gpu_va 0x10000018200).

CLEAN-ROOM: operates only on captured DATA bytes from our own process.

Usage:
  arr.py DUMPDIR [--va 0x10000018200] [--rows START END]   # raw hex rows
  arr.py DUMPDIR --records N                                 # decode N per-attachment records
"""
import argparse, glob, os, re, sys

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR     = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')

def load(path):
    gpu_va = 0; data = bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m = HDR.search(line)
                if m: gpu_va = int(m.group(1),16)
                continue
            m = HEXLINE.match(line)
            if not m: continue
            off = int(m.group(1),16)
            b = bytes.fromhex(m.group(2).replace(' ',''))
            if len(data) < off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)] = b
    return gpu_va, bytes(data)

def find_bo(dumpdir, va):
    for p in sorted(glob.glob(os.path.join(dumpdir,'*.hex'))):
        g,_ = load(p)
        if g == va: return p
    return None

def row(data, off):
    b = data[off:off+16]
    return ' '.join(f'{x:02x}' for x in b)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--va', default='0x10000018200')
    ap.add_argument('--rows', nargs=2, default=None, help='START END (hex) raw dump')
    ap.add_argument('--records', type=int, default=0, help='decode N per-attachment records')
    a = ap.parse_args()
    va = int(a.va,0)
    p = find_bo(a.dumpdir, va)
    if not p:
        print(f'BO {va:#x} not found in {a.dumpdir}'); return 1
    g, data = load(p)
    print(f'# BO {g:#x}  read=0x{len(data):x}  ({os.path.basename(p)})')

    if a.rows:
        s = int(a.rows[0],0); e = int(a.rows[1],0)
        for off in range(s, e, 16):
            print(f'  +{off:#06x}: {row(data,off)}')
        return 0

    if a.records:
        N = a.records
        print('\n## LOAD sub-array  (record base = +0x20 + k*0x20)')
        for k in range(N):
            base = 0x20 + k*0x20
            print(f'  k={k} @+{base:#06x}: {row(data,base)}')
        print('\n## STORE/PBE sub-array  (record base = +0x220 + k*0x20)')
        for k in range(N):
            base = 0x220 + k*0x20
            print(f'  k={k} @+{base:#06x}: {row(data,base)}')
        print('\n## clear-color sub-array  (record base = +0x500 + k*0x18)')
        for k in range(N):
            base = 0x500 + k*0x18
            b = data[base:base+0x18]
            print(f'  k={k} @+{base:#06x}: ' + ' '.join(f'{x:02x}' for x in b))
        return 0

    return 0

if __name__ == '__main__':
    sys.exit(main())
