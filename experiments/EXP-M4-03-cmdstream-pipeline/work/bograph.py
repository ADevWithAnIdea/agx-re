#!/usr/bin/env python3
"""bograph.py -- reconstruct the pointer graph among captured GPU buffer objects.

Part of EXP-0011 (Phase 2 cmdstream decode). Loads the iotrace BO .hex snapshots
(each carries `gpu_va`/`size` in its header) and, for every 8-byte little-endian
value in every BO, tests whether it falls inside another captured BO's
[gpu_va, gpu_va+size) window. The result is the graph of which control structure
points at which -- e.g. the launch descriptor's pointer to the shader-code BO and
to the argument buffer -- purely from observed data.

CLEAN-ROOM: operates only on DATA (bytes that crossed the userspace<->kernel
boundary, captured from our own Metal process). No Apple code is inspected.

Usage:
  bograph.py DUMPDIR                      # full pointer graph (all BOs)
  bograph.py DUMPDIR --from 0x100000b0000 # only pointers out of this BO
  bograph.py DUMPDIR --targets 0x10000090000 0x100000e0000  # extra VAs to name
  bograph.py DUMPDIR --stride 4           # also scan 4-byte-granular offsets (default 8)
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
            b = bytes.fromhex(m.group(2).replace(' ', ''))
            if len(data) < off + len(b):
                data.extend(b'\x00' * (off + len(b) - len(data)))
            data[off:off+len(b)] = b
    return {'path': path, 'gpu_va': gpu_va, 'cpu': cpu, 'size': size, 'data': bytes(data)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dumpdir')
    ap.add_argument('--from', dest='src', default=None, help='only scan this source BO gpu_va')
    ap.add_argument('--targets', nargs='*', default=[], help='extra named VAs')
    ap.add_argument('--stride', type=int, default=8)
    ap.add_argument('--min', default='0x10000000000', help='ignore pointer values below this')
    a = ap.parse_args()

    bos = [load(p) for p in sorted(glob.glob(os.path.join(a.dumpdir, '*.hex')))]
    bos = [b for b in bos if b['gpu_va']]
    if not bos:
        print('no gpu_va-tagged .hex dumps in', a.dumpdir); return 1

    # sortable window list
    wins = sorted(({'va': b['gpu_va'], 'end': b['gpu_va'] + max(b['size'], len(b['data'])),
                    'name': os.path.basename(b['path'])} for b in bos), key=lambda w: w['va'])
    extra = [int(v, 0) for v in a.targets]
    minv = int(a.min, 0)

    def name_of(v):
        for w in wins:
            if w['va'] <= v < w['end']:
                d = v - w['va']
                tag = f"va={w['va']:#x}+{d:#x}" if d else f"va={w['va']:#x}"
                return tag
        return None

    srcva = int(a.src, 0) if a.src else None
    for b in bos:
        if srcva is not None and b['gpu_va'] != srcva:
            continue
        data = b['data']
        hits = []
        for off in range(0, len(data) - 7, a.stride):
            v = int.from_bytes(data[off:off+8], 'little')
            if v < minv or v >= 0x1000000000000:
                continue
            tgt = name_of(v)
            if tgt is None and v in extra:
                tgt = f"(extra {v:#x})"
            if tgt:
                self_tag = ' [SELF]' if b['gpu_va'] <= v < b['gpu_va']+len(data) else ''
                hits.append((off, v, tgt, self_tag))
        if hits:
            print(f"\n=== BO gpu_va={b['gpu_va']:#x} size={b['size']:#x} "
                  f"({os.path.basename(b['path'])}) ===")
            for off, v, tgt, self_tag in hits:
                print(f"  +{off:#06x}: {v:#016x} -> {tgt}{self_tag}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
