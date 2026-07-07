#!/usr/bin/env python3
# Align each fence-probe program against the mem_none / relaxed baseline and report
# the inserted / changed bytes (the 0x07 fence op and its fields).
import re, sys, difflib

rows = {}
for line in open('raw/fenceprobe.txt'):
    m = re.match(r'(\S+) OK ([0-9a-f]+)', line)
    if m:
        rows[m.group(1)] = m.group(2)

def toks(h):
    return [h[i:i+2] for i in range(0, len(h), 2)]

base_label = 'FLAG[mem_none]'
base = toks(rows[base_label])

def diff(lbl):
    if lbl not in rows:
        print(f'  {lbl}: (not present)'); return
    b = toks(rows[lbl])
    sm = difflib.SequenceMatcher(None, base, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        out.append(f'    {tag} base[{i1}:{i2}]={" ".join(base[i1:i2]) or "-"}  ->  new[{j1}:{j2}]={" ".join(b[j1:j2]) or "-"}')
    if not out:
        print(f'  {lbl}: IDENTICAL to baseline (no fence)')
    else:
        print(f'  {lbl}:')
        print('\n'.join(out))

print(f'baseline = {base_label} (len {len(base)} bytes)\n')
for lbl in rows:
    if lbl == base_label: continue
    diff(lbl)
