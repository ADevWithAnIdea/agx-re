#!/usr/bin/env python3
"""dumpscan.py -- correlate iotrace BO/map dumps with our own resource VAs.

Part of EXP-0009 (ROADMAP 0.5). Loads the .hex snapshots iotrace wrote for each
registered GPU buffer object (BO) and searches them, at BYTE granularity, for
caller-supplied 64-/32-bit little-endian needles: our own buffers' GPU VAs,
descriptor/argument-buffer VAs, dispatch dimensions, etc. This is how we locate
where our own shader+resources get encoded into the control/command stream.

CLEAN-ROOM: operates only on DATA (bytes that crossed the userspace<->kernel
boundary, captured from our own Metal process). No Apple code is inspected.

Usage:
  dumpscan.py DUMPDIR --u64 0x10000030000 0x100000e0000 --u32 64 32 2
  dumpscan.py DUMPDIR --list          # summarize every BO (gpu_va, size, entropy)
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
                if m:
                    gpu_va, cpu, size = (int(m.group(i), 16) for i in (1, 2, 3))
                continue
            m = HEXLINE.match(line)
            if not m:
                continue
            off = int(m.group(1), 16)
            hexs = m.group(2).replace(' ', '')
            b = bytes.fromhex(hexs)
            if len(data) < off + len(b):
                data.extend(b'\x00' * (off + len(b) - len(data)))
            data[off:off + len(b)] = b
    return {'path': path, 'gpu_va': gpu_va, 'cpu': cpu, 'size': size, 'data': bytes(data)}

def find_all(hay, needle):
    out, i = [], hay.find(needle)
    while i != -1:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--u64', nargs='*', default=[], help='64-bit LE needles (hex/dec)')
    ap.add_argument('--u32', nargs='*', default=[], help='32-bit LE needles (hex/dec)')
    ap.add_argument('--list', action='store_true', help='summarize BOs')
    a = ap.parse_args()

    bos = [load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir, '*.hex')))]
    if not bos:
        print('no .hex dumps in', a.dumpdir); return 1

    if a.list:
        for b in bos:
            nz = sum(1 for c in b['data'] if c)
            print(f"gpu_va=0x{b['gpu_va']:x} cpu=0x{b['cpu']:x} size=0x{b['size']:x} "
                  f"read=0x{len(b['data']):x} nonzero={nz} {os.path.basename(b['path'])}")
        return 0

    def parse(v): return int(v, 0)
    needles = []
    for v in a.u64:
        n = parse(v); needles.append((v, n.to_bytes(8, 'little')))
    for v in a.u32:
        n = parse(v); needles.append((v, (n & 0xffffffff).to_bytes(4, 'little')))

    for label, nb in needles:
        print(f"\n=== needle {label} (LE {nb.hex()}) ===")
        hits = 0
        for b in bos:
            for off in find_all(b['data'], nb):
                gva = b['gpu_va'] + off if b['gpu_va'] else 0
                print(f"  {os.path.basename(b['path'])} @0x{off:x} "
                      f"(gpu_va 0x{gva:x})")
                hits += 1
        if not hits:
            print("  (not found)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
