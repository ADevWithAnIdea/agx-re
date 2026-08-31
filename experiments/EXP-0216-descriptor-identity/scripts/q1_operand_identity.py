#!/usr/bin/env python3
"""EXP-0216 Q1 — operand identity from the committed bytes.

PRE-STATED (see PRE_REGISTRATION.md) before any record was opened:

  Geometry test G.  For a suspect (row `M.F`, citation E) whose records declare
  span S_d = (fstart,fwidth) while db.json now says S_c:
     * reading R_d ("the sweep moved the DECLARED bits")  predicts
         value == bits(bytes, S_d)  on ~all records, and disagreement at S_c;
     * reading R_c ("the sweep moved the CURRENT bits")   predicts the reverse.
     * If BOTH hold, the two spans coincide on the dispatched encodings and the
       question is undecidable from geometry.

  Identity test I (EXP-0154 H3 release-on-read oracle, already committed).
  A source operand byte in these carriers selects a GPR.  Reading a GPR as a
  32-bit source ZEROES it.  So for every record the register that came back 0
  while its seed was non-zero names the register the swept descriptor selected.
     * If, over a dense byte sweep, zeroed_reg == (value >> k) for a fixed k,
       the swept bits ARE an operand register selector -- a hardware fact that
       owes nothing to the field's name.
     * The ARITHMETIC then separates the operand SLOTS: with distinct seeds,
       substituting a register into a multiplicand changes the result as a
       product, into the addend as a sum.  Predicted r0 is computed by a host
       oracle from the seeds for each candidate slot assignment BEFORE the
       observed r0 is compared.

Neither test is allowed to consult the field name.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import (BY_MNEM, REPO, bits, dump, iter_records, match_ok,  # noqa
                     outcome_of, span_of)

SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}

# The 26 suspects EXP-0215 listed in analysis/suspect_citations.json D.
SUSPECTS = json.loads(
    (REPO / "experiments" / "EXP-0215-citation-repair" / "analysis"
     / "suspect_citations.json").read_text())["D_different_bits_same_name"]


def geometry(mnem, field, expdir):
    cur = span_of(mnem, field)
    agree_d = agree_c = n = 0
    declared = Counter()
    dvals_d, dvals_c, dreq = set(), set(), set()
    same_span = None
    outcomes = Counter()
    ex = None
    for rel, ln, r in iter_records(expdir, mnem, field):
        v = r.get("value")
        if not isinstance(v, int):
            continue
        fs, fw = r.get("fstart"), r.get("fwidth")
        if fs is None or fw is None:
            continue
        n += 1
        declared[(fs, fw)] += 1
        dreq.add(v)
        bd = bits(r["bytes"], fs, fw)
        bc = bits(r["bytes"], cur[0], cur[1]) if cur else None
        if bd is not None:
            dvals_d.add(bd)
            if bd == v:
                agree_d += 1
        if bc is not None:
            dvals_c.add(bc)
            if bc == v:
                agree_c += 1
        if same_span is None:
            same_span = True
        if bd != bc:
            same_span = False
        outcomes[outcome_of(r)] += 1
        if ex is None:
            ex = {"file": rel, "line": ln, "bytes": r["bytes"], "value": v}
    return {
        "mnem": mnem, "field": field, "exp": expdir,
        "current_span": cur,
        "declared_spans": {str(k): v for k, v in declared.items()},
        "n_records_with_value_and_bytes": n,
        "gateA_agree_at_declared": agree_d,
        "gateA_agree_at_current": agree_c,
        "distinct_requested": len(dreq),
        "distinct_decoded_at_declared": len(dvals_d),
        "distinct_decoded_at_current": len(dvals_c),
        "spans_coincide_on_all_dispatched_bytes": same_span,
        "outcomes": dict(outcomes),
        "example": ex,
    }


def zeroed_regs(r):
    """Registers whose seed was non-zero but which came back 0."""
    obs = (r.get("observed") or {}).get("regs")
    if not isinstance(obs, list) or len(obs) < 16:
        return None
    return [i for i in range(16) if SEED_I.get(i, 0) != 0 and obs[i] == 0]


def identity_oracle(mnem, field, expdir, byte_lo=None):
    """Map requested value -> which register was released-on-read, and the
    observed destination value. Pure observation; no name is consulted."""
    rows = []
    for rel, ln, r in iter_records(expdir, mnem, field):
        v = r.get("value")
        obs = (r.get("observed") or {}).get("regs")
        if not isinstance(v, int) or not isinstance(obs, list) or len(obs) < 16:
            continue
        rows.append({
            "value": v, "bytes": r["bytes"], "regs": obs,
            "zeroed": zeroed_regs(r), "r0": obs[0],
            "outcome": outcome_of(r), "file": rel, "line": ln,
            "fstart": r.get("fstart"), "fwidth": r.get("fwidth"),
        })
    return rows


def selector_law(rows):
    """Does zeroed-register track (value >> k) for some k in 0..3?"""
    out = {}
    for k in (0, 1, 2, 3):
        hit = tot = 0
        for row in rows:
            z = row["zeroed"] or []
            tot += 1
            if (row["value"] >> k) & 0xF in z:
                hit += 1
        out[f"reg==(value>>{k})&0xF in zeroed"] = f"{hit}/{tot}"
    # exact single-zeroed-register map
    m = defaultdict(Counter)
    for row in rows:
        z = row["zeroed"] or []
        m[row["value"]][tuple(sorted(z))] += 1
    out["value_to_zeroed"] = {v: dict((str(k2), c) for k2, c in cc.items())
                              for v, cc in sorted(m.items())[:32]}
    return out


def main():
    report = {"geometry": [], "note": __doc__}
    for s in SUSPECTS:
        mnem, field = s["row"].split(".", 1)
        g = geometry(mnem, field, s["dir"])
        g["exp0215_why"] = s["why"]
        g["label"] = s["label"]
        report["geometry"].append(g)
    dump(report, "q1_geometry.json")

    # summary table
    print(f"{'row':28s} {'exp':34s} {'decl':>10s} {'cur':>10s} "
          f"{'n':>6s} {'A@decl':>7s} {'A@cur':>7s} {'coincide':>8s}")
    for g in report["geometry"]:
        decl = ",".join(g["declared_spans"].keys())
        print(f"{g['mnem']+'.'+g['field']:28s} {g['exp']:34s} {decl:>10s} "
              f"{str(g['current_span']):>10s} {g['n_records_with_value_and_bytes']:6d} "
              f"{g['gateA_agree_at_declared']:7d} {g['gateA_agree_at_current']:7d} "
              f"{str(g['spans_coincide_on_all_dispatched_bytes']):>8s}")


if __name__ == "__main__":
    main()
