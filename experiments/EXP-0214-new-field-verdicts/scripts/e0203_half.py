#!/usr/bin/env python3
"""EXP-0214 / EXP-0203 re-derivation: half_alu_fma12 {lensel, mods, srcC} and half_pack.dst.

Run from experiments/EXP-0203-g17p-half-oracle.
"""
import json, collections, os, sys
# GATED runs only.  EXP-0203's PRE_REGISTRATION section 5.5 says of `pilot01`: "Not
# evidence for any field verdict.  Its job is to admit or reject each arm."  So the field
# analyses below use the nine gated runs, and `pilot01` is added back ONLY for the
# half_pack.dst census, where the question is "what values ever reached the hardware at
# all" and including it can only strengthen a negative answer.
GATED = ['g17p_q41','g17p_q42','g17p_q43','g17p_q44','g17p_run21','g17p_run22',
         'g17p_run23','g17p_run31','g17p_run32']
ALL = GATED + ['pilot01']

def load(pred, runs=None):
    for run in (runs if runs is not None else GATED):
        p = 'raw/%s/sweep.jsonl' % run
        if not os.path.exists(p):
            continue
        for L in open(p):
            r = json.loads(L)
            r['_run'] = run
            if pred(r):
                yield r

def main():
    out = {}
    # --- byte+5 == srcC (40,8) -------------------------------------------------
    cells = collections.defaultdict(list)
    for r in load(lambda r: r.get('instr')=='half_alu_fma12' and r.get('field')=='ext'
                            and r.get('byte_index')==5):
        cells[(r['_run'], r['arm'])].append(r)
    t = collections.Counter()
    for k, rs in cells.items():
        ab = bytes.fromhex(rs[0]['anchor'])
        t['n'] += len(rs)
        t['span_only'] += sum(1 for r in rs if all(bytes.fromhex(r['bytes'])[i]==ab[i]
                                                   for i in range(12) if i != 5))
        t['g2'] += sum(1 for r in rs if r['status']=='OK' and r.get('seed_ok')
                       and not r.get('sentinel_bad') and not r.get('victim'))
        t['om'] += sum(1 for r in rs if r['oracle_match'])
        t['g7'] += sum(1 for r in rs if r.get('hw_markers')==4)
        t['unseeded'] += sum(1 for r in rs if (r['oracle'] or {}).get('unseeded'))
    out['srcC'] = {'_runs': 'GATED (9)', 'cells': len(cells), **dict(t)}

    # --- byte+4 == lensel (32,2) + mods (34,6) --------------------------------
    b4 = list(load(lambda r: r.get('instr')=='half_alu_fma12' and r.get('field')=='ext'
                             and r.get('byte_index')==4))
    lensel = collections.defaultdict(collections.Counter)
    for r in b4:
        lensel[bytes.fromhex(r['bytes'])[4] & 3][r.get('hw_markers')] += 1
    out['lensel_markers'] = {'_runs': 'GATED (9)',
                             **{str(k): dict(v) for k, v in sorted(lensel.items())}}
    mods = collections.defaultdict(collections.Counter)
    for r in b4:
        v = bytes.fromhex(r['bytes'])[4]
        if v & 3 != 3:
            continue
        m = v >> 2
        mods[m]['n'] += 1
        mods[m]['oracle_match'] += bool(r['oracle_match'])
        for f in (r.get('semantic_model_fits') or []):
            mods[m]['fit:'+f] += 1
    out['mods_at_lensel3'] = {'_runs': 'GATED (9)',
                              **{str(k): dict(v) for k, v in sorted(mods.items())}}

    # --- half_pack.dst (4,4) ---------------------------------------------------
    nib = collections.Counter(); byarm = collections.defaultdict(collections.Counter)
    swept = collections.Counter()
    for r in load(lambda r: r.get('instr')=='half_pack' and r.get('bytes'), ALL):
        n = bytes.fromhex(r['bytes'])[0] >> 4
        nib[(n, r['field'])] += 1
        byarm[r['arm']][n] += 1
        swept[r['field']] += 1
    out['half_pack_dst'] = {
        '_runs': 'GATED + pilot01',
        'nibble_by_field': {'%d/%s' % k: v for k, v in sorted(nib.items())},
        'nibble_by_arm': {a: dict(sorted(c.items())) for a, c in sorted(byarm.items())},
        'swept_fields': dict(swept),
        'records_with_field_dst': swept.get('dst', 0),
    }
    json.dump(out, sys.stdout, indent=1)

if __name__ == '__main__':
    main()
