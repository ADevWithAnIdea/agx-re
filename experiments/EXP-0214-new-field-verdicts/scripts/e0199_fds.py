#!/usr/bin/env python3
"""EXP-0214 / EXP-0199: frag_depth_store b1_lo (8,1), b1_hi (11,5), b2 (16,8).

The byte+1 sweep is dense 0..255; the descriptor's `match` pins only bits 1..2, so the
question is whether the OTHER six bits of byte+1 (the two new fields) move anything
INSIDE the accepted set.  The observable is the per-pixel colour AND depth readback plus
both surface histogram hashes.

Run from experiments/EXP-0199-g17p-instruction-level.
"""
import json, collections, os, sys
RUNS = ['g17p_conf01','g17p_conf04','g17p_quietconf01','g17p_quietconf02',
        'g17p_run01a','g17p_run02a']

def main():
    rec = collections.defaultdict(dict); led = collections.Counter()
    tbl = collections.defaultdict(dict)
    for run in RUNS:
        p = 'raw/%s/sweep.jsonl' % run
        if not os.path.exists(p):
            continue
        for L in open(p):
            r = json.loads(L)
            if r.get('instr') != 'frag_depth_store' or r.get('field') not in ('byte1', 'byte2'):
                continue
            idx = 1 if r['field'] == 'byte1' else 2
            lg = r.get('ledger') or {}
            led['n'] += 1
            led['checked'] += bool(lg.get('checked'))
            ap = lg.get('actual_prefix')
            if ap:
                led['actual_byte_eq_requested'] += (bytes.fromhex(ap)[idx] == r['value'])
            else:
                led['no_actual_prefix'] += 1
            o = r.get('observed') or {}
            sig = (json.dumps(o.get('col')), json.dumps(o.get('dep')), o.get('ph'), o.get('dh'))
            rec[(run, r.get('carrier') or '(pre-conf)', r['field'])][r['value']] = (r['outcome'], sig)
            tbl[(r['field'], r.get('carrier') or '(pre-conf)', r['value'])][run] = r['outcome']
    out = {'gate_A': dict(led), 'cells': {}}
    for k, m in sorted(rec.items()):
        run, car, fld = k
        d = {'n': len(m), 'outcomes': dict(collections.Counter(v[0] for v in m.values()))}
        if fld == 'byte1':
            acc = sorted(v for v, x in m.items() if x[0] == 'ok')
            d['accepted'] = '%d/256' % len(acc)
            d['accepted_rule_(v&6)==4_holds'] = all((v & 6) == 4 for v in acc)
            d['b1_lo_values_inside_accepted'] = sorted(set(v & 1 for v in acc))
            d['b1_hi_values_inside_accepted'] = len(set(v >> 3 for v in acc))
            d['distinct_hw_signatures_inside_accepted'] = len(set(m[v][1] for v in acc))
        else:
            d['distinct_hw_signatures_over_all_values'] = len(set(v[1] for v in m.values()))
        out['cells']['%s/%s/%s' % k] = d
    out['anomaly_reproduction'] = {
        '%s/%s/%d' % k: v for k, v in sorted(tbl.items())
        if any(o not in ('ok', 'tile_discarded') for o in v.values())}
    json.dump(out, sys.stdout, indent=1)

if __name__ == '__main__':
    main()
