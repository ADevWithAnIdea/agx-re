#!/usr/bin/env python3
"""Audit: for each of EXP-0181's 30 refreshed `_instruction` labels, scan every
committed raw/*.jsonl record whose `bytes` column satisfies that mnemonic's db.json
`match` at some byte offset, and tally the SCORING REGIME (host oracle vs baseline
movement) per experiment/run.  Read-only."""
import json, glob, os, re, collections, sys

ROOT = '/Users/user/asahi_re/public/agx-re'
db = json.load(open(os.path.join(ROOT, 'tools/agx-isa/db.json')))
SPEC = {}
for i in db['instructions']:
    SPEC[i['mnemonic']] = (i.get('length'), [(m['start'], m['width'], m['value'])
        if isinstance(m, dict) else tuple(m) for m in (i.get('match') or [])])

W = """bf_add_dst bf_fma_dst cvt_bf16 cvt_f2h cvt_f2h_dst cvt_i2f falu3 falu3_ext
frag_depth_store frame_marker_compact h_coord_hi h_coord_hi_ext hminmax irotate
iter_flat mov_imm mov_zext16 n2_op6 n3_mov pack_convert psel ret_luse rtq_state_move
sel sfu_marker shift_amt_move sr_read_wide uniform_mov vary_slot vtx_coord_xform
iter_at get_sr call""".split()

HEX = re.compile(r'^[0-9a-fA-F]+$')

def fits(word, nbytes, mn):
    L, match = SPEC[mn]
    if not match:
        return False
    L = L or nbytes
    for d in range(0, max(1, nbytes - L + 1)):
        iw = word >> (8 * d)
        if all(((iw >> s) & ((1 << w) - 1)) == v for s, w, v in match):
            return True
    return False

stats = collections.defaultdict(lambda: collections.Counter())
files = sorted(glob.glob(os.path.join(ROOT, 'experiments/*/raw/**/*.jsonl'), recursive=True))
for f in files:
    rel = os.path.relpath(f, os.path.join(ROOT, 'experiments'))
    exp = rel.split('/')[0]
    run = rel.split('/')[2] if len(rel.split('/')) > 3 else os.path.basename(os.path.dirname(f))
    try:
        fh = open(f, errors='replace')
    except OSError:
        continue
    for line in fh:
        line = line.strip()
        if not line or line[0] != '{':
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        b = r.get('bytes')
        if not isinstance(b, str) or not b or not HEX.match(b) or len(b) % 2:
            continue
        nb = len(b) // 2
        try:
            word = int.from_bytes(bytes.fromhex(b), 'little')
        except Exception:
            continue
        o = r.get('oracle')
        has_o = o not in (None, {}, '', [])
        for mn in W:
            if mn not in SPEC:
                continue
            if fits(word, nb, mn):
                k = (mn, exp, run)
                stats[k]['n'] += 1
                stats[k]['oracle' if has_o else 'nooracle'] += 1
                if has_o:
                    stats[k]['oracle_match' if r.get('match') is True else 'oracle_nomatch'] += 1
json.dump({'|'.join(k): dict(v) for k, v in stats.items()},
          open(os.path.join(ROOT, 'experiments/EXP-0189-closing-audit/work/oracle_scan.json'), 'w'), indent=0)
print("wrote", len(stats), "cells")
