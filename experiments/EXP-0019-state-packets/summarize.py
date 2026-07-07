#!/usr/bin/env python3
"""summarize.py -- extract per-BO single-word diffs from EXP-0019 bodiff outputs.

Reads analysis/diff_<label>.txt files (bodiff dir-vs-dir output) and prints, for a
requested set of control BOs, the (offset, A_word -> B_word) changes for each label.
Filters the known gpu_va=0x0 pseudo-BO artifact and the 0x10000130000+0x534 per-run
counter. Pure data reformatting -- no Apple code touched.
"""
import re, sys, os, glob

DIFF = re.compile(r'\+0x([0-9a-f]+):\s+0x([0-9a-f]+)\s*->\s*0x([0-9a-f]+)')
HDR  = re.compile(r'=== gpu_va=0x([0-9a-f]+)')

def parse(path):
    """return {gpu_va(int): [(off, a, b)]}"""
    out = {}
    cur = None
    for line in open(path):
        m = HDR.search(line)
        if m:
            cur = int(m.group(1), 16)
            out.setdefault(cur, [])
            continue
        m = DIFF.search(line)
        if m and cur is not None:
            off = int(m.group(1), 16); a = int(m.group(2), 16); b = int(m.group(3), 16)
            if cur == 0x10000130000 and off == 0x534:   # per-run counter
                continue
            out[cur].append((off, a, b))
    return out

def show(labels, bos, adir='raw/analysis'):
    for lab in labels:
        p = os.path.join(adir, f'diff_{lab}.txt')
        if not os.path.exists(p):
            print(f'{lab}: MISSING'); continue
        d = parse(p)
        parts = []
        for bo in bos:
            for off, a, b in d.get(bo, []):
                parts.append(f'{bo:#x}+{off:#05x}:{a:#010x}->{b:#010x}')
        print(f'{lab:22s} ' + ('  '.join(parts) if parts else '(no change in tracked BOs)'))

if __name__ == '__main__':
    adir = 'raw/analysis'
    bos = [int(x, 16) for x in sys.argv[1].split(',')] if len(sys.argv) > 1 else [0x58000, 0x18000]
    labels = sys.argv[2].split(',') if len(sys.argv) > 2 else []
    if not labels:
        labels = sorted(os.path.basename(p)[5:-4] for p in glob.glob(os.path.join(adir, 'diff_*.txt')))
    show(labels, bos, adir)
