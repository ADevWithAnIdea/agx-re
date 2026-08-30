#!/usr/bin/env python3
"""EXP-0160 desk analysis of EXP-0154's committed raw sweep records.

Purely offline: re-reads the append-only JSONL evidence a prior committed
experiment left behind and prints, per target field, the per-value register
delta. No hardware is touched. Used ONLY to design this experiment's probe
(which model to test); nothing here is promoted.

CLEAN-ROOM: reads our own committed raw observations. No Apple binary.
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
E154 = REPO / "experiments" / "EXP-0154-g17p-emit-alu"
TARGETS = {
    ("falu2_ext", "ctrl"), ("falu3", "op"), ("falu3_ext", "op"),
    ("iminmax", "srcB"), ("isel8", "cmp_mode"), ("imad", "srcC_desc"),
    ("half_pack", "src"),
}

def load(run):
    out = defaultdict(dict)
    p = E154 / "raw" / run / "sweep.jsonl"
    for ln in p.open():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        k = (r["instr"], r["field"])
        if k in TARGETS:
            out[k][r["value"]] = r
    return out

def main():
    runs = sys.argv[1:] or ["g17p_20260829_run02", "g17p_20260829_run04"]
    L = [load(r) for r in runs]
    for k in sorted(TARGETS):
        instr, field = k
        a, b = L[0].get(k, {}), (L[1].get(k, {}) if len(L) > 1 else {})
        vals = sorted(set(a) | set(b))
        print("=" * 78)
        print("%s.%s   tested=%d  in_both=%d" % (instr, field, len(vals),
              len(set(a) & set(b))))
        if not vals:
            continue
        r0 = a.get(vals[0]) or b.get(vals[0])
        print("  carrier:", r0["carrier"], " bytes(anchor-ish):", r0["bytes"])
        od = r0["oracle"]["digest"]
        base = [int(od[i*8:(i+1)*8], 16) for i in range(16)] if od else None
        print("  baseline regs:", base)
        oc = Counter(a[v]["outcome"] for v in a)
        print("  outcomes run1:", dict(oc))
        # per-value delta
        rows = []
        for v in vals:
            r = a.get(v) or b.get(v)
            obs = r["observed"]["regs"]
            if not obs:
                rows.append((v, r["outcome"], "NO-DUMP", ""))
                continue
            rel = [i for i in range(16) if base[i] != 0 and obs[i] == 0]
            wr = [(i, base[i], obs[i]) for i in range(16)
                  if obs[i] != base[i] and obs[i] != 0]
            agree = (v in a and v in b and a[v]["outcome"] == b[v]["outcome"]
                     and a[v]["observed"]["digest"] == b[v]["observed"]["digest"])
            rows.append((v, r["outcome"], rel, wr, agree))
        for row in rows:
            if len(row) == 5:
                v, oc1, rel, wr, agree = row
                print("   %3d 0x%02x %-12s rel=%-16s wr=%-40s %s"
                      % (v, v, oc1, rel, wr, "" if agree else "DISAGREE/1RUN"))
            else:
                print("   %3d 0x%02x %-12s %s" % (row[0], row[0], row[1], row[2]))

if __name__ == "__main__":
    main()
