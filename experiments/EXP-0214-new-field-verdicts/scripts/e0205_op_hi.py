#!/usr/bin/env python3
"""EXP-0214 / EXP-0205: is simd_reduce.op_hi (11,5) inert within the tested envelope?

The test is period-8: does the HARDWARE observable depend only on byte+1 bits [2:0]?
`observed.gputime_ns` MUST be excluded -- it is a nondeterministic timing measurement,
and including it makes every dispatch look different (the same defect EXP-0202 found in
tools/agx-isa/wave_audit.py).  Including the derived `outcome` label is equally wrong:
it is scored against a per-VALUE oracle, so it varies with op_hi even when the silicon
does not.

Run from experiments/EXP-0205-g17p-simd-subgroup.
"""
import json, collections, os, sys
RUNS = ['g17p_quiet01','g17p_quiet02','g17p_quiet03','g17p_quiet04',
        'g17p_20260830_runB01','g17p_20260830_runB02']
HW = ('vals_u32','sec_u32','plan2_u32','unwritten','sentinel_ok','tail_poison_ok','status')

def main():
    cells = collections.defaultdict(dict)
    led = collections.Counter()
    for run in RUNS:
        p = 'raw/%s/sweep.jsonl' % run
        if not os.path.exists(p):
            continue
        for L in open(p):
            r = json.loads(L)
            if r.get('instr') != 'simd_reduce' or r.get('field') != 'op' or r.get('role') != 'target':
                continue
            lg = r.get('ledger') or {}
            led['n'] += 1
            led['bytes_eq'] += bool(lg.get('requested_bytes_equal_actual'))
            led['decoded_eq'] += bool(lg.get('requested_equals_decoded'))
            o = r['observed']
            cells[(run, r['arm'])][bytes.fromhex(r['bytes'])[1]] = \
                json.dumps({k: o.get(k) for k in HW}, sort_keys=True)
    res = {'gate_A': dict(led), 'cells': {}}
    p8 = 0
    for k, m in sorted(cells.items()):
        grp = collections.defaultdict(set)
        for v, o in m.items():
            grp[v & 7].add(o)
        ok = all(len(s) == 1 for s in grp.values())
        p8 += ok
        res['cells']['%s/%s' % k] = {
            'n': len(m),
            'op_hi_values': len(set(v >> 3 for v in m)),
            'period8': ok,
            'distinct_hw_observables_per_residue': [len(grp[i]) for i in sorted(grp)],
        }
    res['period8_cells'] = '%d/%d' % (p8, len(cells))
    byav = collections.defaultdict(dict)
    for (run, arm), m in cells.items():
        for v, o in m.items():
            byav[(arm, v)][run] = o
    res['cross_run_disagreements'] = '%d/%d' % (
        sum(1 for v in byav.values() if len(set(v.values())) > 1), len(byav))
    json.dump(res, sys.stdout, indent=1)

if __name__ == '__main__':
    main()
