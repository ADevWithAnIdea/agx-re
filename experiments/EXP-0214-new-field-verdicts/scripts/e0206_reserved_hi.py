#!/usr/bin/env python3
"""EXP-0214 / EXP-0206: pop_reconverge.reserved_hi (40,8).

The parent `reserved` was (32,16) and was SAMPLED, not swept: 52 of 65,536.  The high
byte is only interpretable where the sibling LOW byte is zero, because the low byte is
load-bearing on the one carrier that can see it.  So stratify.

Run from experiments/EXP-0206-g17p-cf-scope.
"""
import json, collections, os, sys
RUNS = ['g17p_20260830_run03','g17p_20260830_run04','g17p_20260830_run05',
        'g17p_20260830_run07','g17p_quiet02',
        'g17p_e0213_S1_cf_nl2','g17p_e0213_S2_cf_nl2',
        'g17p_e0213_S1_cl_atomic','g17p_e0213_S2_cl_atomic']

def span(hx, s, w):
    return (int.from_bytes(bytes.fromhex(hx), 'little') >> s) & ((1 << w) - 1)

def sig(r):
    o = r.get('observed')
    if isinstance(o, dict):
        o = {k: v for k, v in o.items() if k != 'gputime_ns'}
    return json.dumps({'vals': r.get('vals'), 'observed': o, 'outcome': r['outcome']}, sort_keys=True)

def main():
    rec = collections.defaultdict(dict); led = collections.Counter()
    for run in RUNS:
        p = 'raw/%s/sweep.jsonl' % run
        if not os.path.exists(p):
            continue
        for L in open(p):
            r = json.loads(L)
            if r.get('instr') != 'pop_reconverge' or r.get('field') != 'reserved':
                continue
            lg = r.get('ledger') or {}
            ab = lg.get('actual_bytes') or r.get('bytes')
            led['n'] += 1
            led['hi_span_decodes'] += (span(ab, 40, 8) == (r['value'] >> 8))
            rec[(run, r['carrier'])][r['value']] = r
    out = {'gate_A_hi_span_decodes': '%d/%d' % (led['hi_span_decodes'], led['n']), 'cells': {}}
    for k, m in sorted(rec.items()):
        lo0 = [v for v in m if (v & 255) == 0]
        out['cells']['%s/%s' % k] = {
            'sampled_16bit_values': len(m),
            'distinct_high_bytes_dispatched': len(set(v >> 8 for v in m)),
            'high_bytes_at_low_byte_zero': sorted(set(v >> 8 for v in lo0)),
            'cases_at_low_byte_zero': len(lo0),
            'distinct_hw_signatures_at_low_byte_zero': len(set(sig(m[v]) for v in lo0)),
            'outcomes_at_low_byte_zero': dict(collections.Counter(m[v]['outcome'] for v in lo0)),
            'outcomes_at_low_byte_nonzero':
                dict(collections.Counter(m[v]['outcome'] for v in m if (v & 255) != 0)),
        }
    json.dump(out, sys.stdout, indent=1)

if __name__ == '__main__':
    main()
