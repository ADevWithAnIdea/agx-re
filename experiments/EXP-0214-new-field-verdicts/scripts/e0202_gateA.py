#!/usr/bin/env python3
"""EXP-0214 / EXP-0202: Gate A + coverage for the four NEW irotate sub-spans.

The driver's own `ledger_ok` compares the requested value against the tokenizer's
decode of the WHOLE parent field (`operands` was 40 bits), so it reads False on every
byte-wise arm even though the dispatch was exact.  EXP-0202's own analysis/verdicts.py
already re-derives it; this reproduces that, keyed on the POST-EXP-0212 spans, which
are now the db fields themselves.

Run from experiments/EXP-0202-g17p-int-shift-convert.
"""
import json, collections, os, sys
RUNS = ['g17p_quiet03','g17p_quiet04','g17p_20260830_run03','g17p_20260830_run04']
SUB = {24: 'rot_dst', 32: 'op_enable', 40: 'rot_src', 56: 'amt_tail'}

def span(hx, s, w):
    return (int.from_bytes(bytes.fromhex(hx), 'little') >> s) & ((1 << w) - 1)

def main():
    acc = collections.defaultdict(list)
    for run in RUNS:
        p = 'raw/%s/sweep.jsonl' % run
        if not os.path.exists(p):
            continue
        for L in open(p):
            r = json.loads(L)
            if (r.get('instr') == 'irotate' and r.get('role') == 'target'
                    and r.get('width') == 8 and r.get('start') in SUB):
                r['_run'] = run
                acc[r['start']].append(r)
    out = {}
    for st, rs in sorted(acc.items()):
        ga = sum(1 for r in rs
                 if r['requested_bytes'] == r['actual_bytes']
                 and span(r['actual_bytes'], st, 8) == (r['value'] & 255))
        perarm = collections.defaultdict(set)
        for r in rs:
            perarm[r['arm']].add(r['actual_bytes'])
        byav = collections.defaultdict(dict)
        for r in rs:
            byav[(r['arm'], r['value'])][r['_run']] = r['outcome']
        out[SUB[st]] = {
            'start': st, 'width': 8, 'encodable_range': 256,
            'arms': sorted(perarm), 'runs': sorted(set(r['_run'] for r in rs)),
            'cases': len(rs),
            'gate_A_requested_bytes_eq_actual_and_span_decodes': '%d/%d' % (ga, len(rs)),
            'distinct_requested_values': len(set(r['value'] for r in rs)),
            'distinct_actual_encodings_per_arm': {a: len(s) for a, s in sorted(perarm.items())},
            'outcomes': dict(collections.Counter(r['outcome'] for r in rs)),
            'sem_checked': sum(1 for r in rs if r.get('sem_checked')),
            'sem_match': sum(1 for r in rs if r.get('sem_match')),
            'oracle_rules': dict(collections.Counter((r.get('oracle') or {}).get('rule') for r in rs)),
            'values_reproducing_carrier_vector':
                sorted(set(r['value'] for r in rs if r['outcome'] in ('ok', 'unexpected_ok'))),
            'values_faulting': sorted(set(r['value'] for r in rs if r['outcome'] == 'fault')),
            'cross_run_outcome_disagreements':
                '%d/%d' % (sum(1 for v in byav.values() if len(set(v.values())) > 1), len(byav)),
        }
    json.dump(out, sys.stdout, indent=1)

if __name__ == '__main__':
    main()
