#!/usr/bin/env python3
"""EXP-0154 analysis: raw sweep records -> per-field verdicts (G17P).

  python3 analysis/verdicts.py raw/g17p_20260829_run01 raw/g17p_20260829_run02

Applies the promotion rule frozen in PRE_REGISTRATION.md section 7 and emits
`analysis/field_verdicts.json` in FIELD-SWEEP-PROTOCOL section 5 schema.

Nothing here re-runs hardware; it is a pure function of the committed raw logs.
"""
from __future__ import print_function

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H          # noqa: E402
import casematrix as CM          # noqa: E402

GOOD = ("hardware-run", "isolated-byte-diff")


def load(rundir):
    recs = {}
    p = Path(rundir) / "sweep.jsonl"
    for ln in p.open():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        recs[r["idx"]] = r            # last write wins (resume-safe)
    return recs


def mask_rule(ok_vals, all_vals, width):
    """Smallest (MASK, V) such that every ok value satisfies (v & MASK) == V.
    Returns (mask, val, exact, exceptions)."""
    ok = set(ok_vals)
    if not ok:
        return (None, None, False, None)
    mask = 0
    val = 0
    for b in range(width):
        s = set((v >> b) & 1 for v in ok)
        if len(s) == 1:
            mask |= 1 << b
            val |= s.pop() << b
    pred = set(v for v in all_vals if (v & mask) == val)
    exceptions = len(pred ^ ok)
    return (mask, val, exceptions == 0, exceptions)


REG_MODELS = {
    "v>>1": lambda v: v >> 1,
    "(v>>1)&63": lambda v: (v >> 1) & 63,
    "v>>2": lambda v: v >> 2,
    "v&127": lambda v: v & 127,
    "v&15": lambda v: v & 15,
    "v": lambda v: v,
}


def register_maps(recs_for_field, base_regs):
    """H3: which register did each swept value RELEASE (read-and-zero), and
    which register did it WRITE? Both are read straight out of the 16-register
    dump and are independent of the instruction's arithmetic."""
    released = {}
    written = {}
    for v, r in sorted(recs_for_field.items()):
        obs = r["observed"]["regs"]
        if not obs:
            continue
        rel = [i for i in range(H.N_REGS)
               if base_regs[i] != 0 and obs[i] == 0]
        wr = [i for i in range(H.N_REGS)
              if obs[i] != base_regs[i] and obs[i] != 0]
        released[v] = rel
        written[v] = wr
    scores = {}
    for name, f in REG_MODELS.items():
        hits = tot = 0
        for v, rel in released.items():
            if len(rel) == 1:
                tot += 1
                if rel[0] == f(v) % H.N_REGS or rel[0] == f(v):
                    hits += 1
        if tot:
            scores[name] = "%d/%d" % (hits, tot)
    return released, written, scores


def main():
    runs = sys.argv[1:]
    if not runs:
        print("usage: verdicts.py <rundir> [<rundir2> ...]"); return 2
    loaded = [load(r) for r in runs]
    rep = json.loads((EXP / "work" / "anchor_report.json").read_text()) \
        if (EXP / "work" / "anchor_report.json").exists() else \
        json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = {c["idx"]: c for c in CM.build_cases(rep)}

    # ---- cross-run gate --------------------------------------------------
    gated = {}
    disagree = Counter()
    victim_excluded = 0
    for idx, c in cases.items():
        rs = [L.get(idx) for L in loaded]
        rs = [r for r in rs if r is not None]
        if not rs:
            continue
        if any(r.get("victim") for r in rs):
            victim_excluded += 1
            continue
        ocs = set(r["outcome"] for r in rs)
        if len(ocs) > 1:
            disagree[(c["arm"], c["field"])] += 1
            continue
        r = dict(rs[0])
        r["n_runs"] = len(rs)
        gated[idx] = r

    # ---- baselines per arm ------------------------------------------------
    base_regs = {}
    for idx, r in gated.items():
        c = cases[idx]
        if c["field"] == "__falsifier_byte0":
            continue
        if r["oracle"]["digest"] and c["arm"] not in base_regs:
            d = r["oracle"]["digest"]
            base_regs[c["arm"]] = [int(d[i * 8:(i + 1) * 8], 16) for i in range(16)]

    # ---- falsifiers -------------------------------------------------------
    fals = {}
    for idx, r in gated.items():
        if cases[idx]["field"] == "__falsifier_byte0":
            fals[cases[idx]["arm"]] = r["outcome"]

    # ---- group by (arm, instr, field[, byte_index]) ----------------------
    groups = defaultdict(dict)
    for idx, r in gated.items():
        c = cases[idx]
        if c["field"].startswith("__"):
            continue
        key = (c["arm"], c["instr"], c["field"], c.get("byte_index"))
        groups[key][c["value"]] = r

    out = {}
    for (arm, instr, field, bidx), recs in sorted(groups.items()):
        vals = sorted(recs)
        width = cases_width(cases, arm, field, bidx)
        okv = [v for v in vals if recs[v]["outcome"] == "ok"]
        oc = Counter(recs[v]["outcome"] for v in vals)
        mask, mval, exact, exc = mask_rule(okv, vals, width)
        rel, wr, scores = register_maps(recs, base_regs.get(arm, [0] * 16))

        dense = (len(vals) == (1 << width))
        fal_ok = fals.get(arm) != "ok"
        # PRE_REGISTRATION section 7: promotion requires an identical per-value
        # outcome map in BOTH gated runs. A value only one run reached is not
        # gated evidence, so the whole field stays `untested`.
        two_runs = all(recs[v].get("n_runs", 1) >= 2 for v in vals)
        if not two_runs:
            label, why = "untested", ("not covered by both gated runs "
                                      "(%d/%d values have 2 runs)"
                                      % (sum(1 for v in vals
                                             if recs[v].get("n_runs", 1) >= 2), len(vals)))
        elif not okv:
            label, why = "untested", "no value reproduced the anchor"
        elif len(okv) == len(vals):
            label, why = "hardware-run", "INERT across the whole encodable range"
        elif exact and dense and fal_ok:
            label, why = "hardware-run", "exact rule (v & 0x%02x) == 0x%02x, 0 exceptions" % (mask, mval)
        elif exc is not None and exc <= 2 and dense and fal_ok:
            label, why = "isolated-byte-diff", "rule (v & 0x%02x) == 0x%02x with %d exception(s)" % (mask, mval, exc)
        else:
            label, why = "untested", "no exact rule; %d/%d values ok" % (len(okv), len(vals))
        if bidx is not None and label == "hardware-run":
            # a byte of a wider raw field: the full multi-byte space is NOT claimed
            label = "isolated-byte-diff"
            why += "; swept BYTE-WISE only, full field space not claimed"

        key = "%s.%s" % (instr, field) + ("" if bidx is None else "@byte+%d" % bidx)
        entry = {
            "label": label,
            "range": "%d values tested (%s over %d-bit domain)"
                     % (len(vals), "dense" if dense else "sampled", width),
            "target": "G17P",
            "evidence": ["EXP-0154"],
            "semantics": why,
            "note": "carrier %s; outcomes %s; ok at %s"
                    % (recs[vals[0]]["carrier"], dict(oc), compact(okv)),
            "arm": arm,
            "falsifier_fired": fal_ok,
            "n_runs_gated": recs[vals[0]].get("n_runs", 1),
        }
        if scores:
            entry["register_model_scores"] = scores
        if bidx is None and width <= 8 and len(okv) <= 40:
            entry["released_reg_map"] = dict((str(v), rel.get(v)) for v in okv)
        out[key] = entry

    out["_meta"] = {
        "experiment": "EXP-0154", "target": "G17P",
        "runs": runs, "gated_cases": len(gated),
        "victim_excluded": victim_excluded,
        "cross_run_disagreements": dict((("%s.%s" % k), v)
                                        for k, v in disagree.items()),
        "falsifiers": fals,
        "promotion_rule": "PRE_REGISTRATION.md section 7",
        "skipped_instructions": CM.SKIPPED,
    }
    p = HERE / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", p, "fields:", len(out) - 1)
    lab = Counter(v["label"] for k, v in out.items() if not k.startswith("_"))
    print(dict(lab))


def compact(vs):
    if not vs:
        return "{}"
    if len(vs) > 24:
        return "{%d values}" % len(vs)
    out, i = [], 0
    while i < len(vs):
        j = i
        while j + 1 < len(vs) and vs[j + 1] == vs[j] + 1:
            j += 1
        out.append("0x%x" % vs[i] if i == j else "0x%x-0x%x" % (vs[i], vs[j]))
        i = j + 1
    return "{%s}" % ", ".join(out)


_W = {}


def cases_width(cases, arm, field, bidx):
    if bidx is not None:
        return 8
    k = (arm, field)
    if k not in _W:
        for c in cases.values():
            if c["arm"] == arm and c["field"] == field and c.get("fwidth"):
                _W[k] = c["fwidth"]
                break
        else:
            _W[k] = 8
    return _W[k]


if __name__ == "__main__":
    sys.exit(main() or 0)
